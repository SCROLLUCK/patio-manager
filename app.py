from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
from datetime import datetime, date
import csv
import io
import re
import json
import tempfile
import os
import pdfplumber

app = Flask(__name__)
app.secret_key = 'patio_bebidas_2024'

DATABASE = 'bebidas.db'

CATEGORIAS = [
    'Cerveja',
    'Vinho / Espumante',
    'Refrigerante',
    'Água',
    'Suco',
    'Energético / Isotônico',
    'Chá / Kombucha',
    'Destilados (Whisky, Vodka, Gin, Rum)',
    'Licor / Aperitivo',
    'Cachaça',
    'Bebida Mista',
    'Outros',
]


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bebidas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                categoria TEXT NOT NULL,
                validade DATE NOT NULL,
                quantidade INTEGER NOT NULL,
                valor REAL DEFAULT 0.0,
                data_registro DATETIME DEFAULT (datetime('now', 'localtime'))
            )
        ''')
        try:
            conn.execute('ALTER TABLE bebidas ADD COLUMN valor REAL DEFAULT 0.0')
        except Exception:
            pass
        conn.commit()


_SORT_COLS = {
    'validade':  'validade',
    'quantidade': 'quantidade',
    'valor':     'valor',
    'total':     'quantidade * valor',
    'registro':  'data_registro',
}

@app.route('/')
def index():
    busca = request.args.get('busca', '')
    categorias_filtro = request.args.getlist('categoria')
    sort  = request.args.get('sort', 'validade')
    order = request.args.get('order', 'asc')

    if sort not in _SORT_COLS:
        sort = 'validade'
    if order not in ('asc', 'desc'):
        order = 'asc'

    query = 'SELECT * FROM bebidas WHERE 1=1'
    params = []

    if busca:
        query += ' AND nome LIKE ?'
        params.append(f'%{busca}%')

    if categorias_filtro:
        placeholders = ','.join('?' * len(categorias_filtro))
        query += f' AND categoria IN ({placeholders})'
        params.extend(categorias_filtro)

    query += f' ORDER BY {_SORT_COLS[sort]} {order.upper()}'

    today = date.today().isoformat()

    with get_db() as conn:
        bebidas = conn.execute(query, params).fetchall()
        total = conn.execute('SELECT COUNT(*) as c FROM bebidas').fetchone()['c']

    return render_template('index.html',
                           bebidas=bebidas,
                           today=today,
                           categorias=CATEGORIAS,
                           busca=busca,
                           categorias_filtro=categorias_filtro,
                           total=total,
                           sort=sort,
                           order=order)


@app.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        categoria = request.form.get('categoria', '').strip()
        validade = request.form.get('validade', '').strip()
        quantidade = request.form.get('quantidade', '').strip()
        valor = request.form.get('valor', '0').strip().replace(',', '.')

        erros = []
        if not nome:
            erros.append('Nome é obrigatório.')
        if not categoria:
            erros.append('Categoria é obrigatória.')
        if not validade:
            erros.append('Validade é obrigatória.')
        if not quantidade or not quantidade.isdigit() or int(quantidade) < 0:
            erros.append('Quantidade deve ser um número válido.')
        try:
            valor = float(valor) if valor else 0.0
            if valor < 0:
                raise ValueError
        except ValueError:
            erros.append('Valor deve ser um número válido.')

        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('cadastrar.html', categorias=CATEGORIAS,
                                   form=request.form)

        with get_db() as conn:
            conn.execute(
                'INSERT INTO bebidas (nome, categoria, validade, quantidade, valor) VALUES (?, ?, ?, ?, ?)',
                (nome, categoria, validade, int(quantidade), valor)
            )
            conn.commit()

        flash(f'"{nome}" cadastrada com sucesso!', 'success')
        return redirect(url_for('index'))

    return render_template('cadastrar.html', categorias=CATEGORIAS, form={})


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    with get_db() as conn:
        bebida = conn.execute('SELECT * FROM bebidas WHERE id = ?', (id,)).fetchone()

    if not bebida:
        flash('Bebida não encontrada.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        categoria = request.form.get('categoria', '').strip()
        validade = request.form.get('validade', '').strip()
        quantidade = request.form.get('quantidade', '').strip()
        valor = request.form.get('valor', '0').strip().replace(',', '.')

        erros = []
        if not nome:
            erros.append('Nome é obrigatório.')
        if not categoria:
            erros.append('Categoria é obrigatória.')
        if not validade:
            erros.append('Validade é obrigatória.')
        if not quantidade or not quantidade.isdigit() or int(quantidade) < 0:
            erros.append('Quantidade deve ser um número válido.')
        try:
            valor = float(valor) if valor else 0.0
            if valor < 0:
                raise ValueError
        except ValueError:
            erros.append('Valor deve ser um número válido.')

        if erros:
            for e in erros:
                flash(e, 'danger')
            return render_template('editar.html', bebida=bebida, categorias=CATEGORIAS)

        with get_db() as conn:
            conn.execute(
                'UPDATE bebidas SET nome=?, categoria=?, validade=?, quantidade=?, valor=? WHERE id=?',
                (nome, categoria, validade, int(quantidade), valor, id)
            )
            conn.commit()

        flash(f'"{nome}" atualizada com sucesso!', 'success')
        return redirect(url_for('index'))

    return render_template('editar.html', bebida=bebida, categorias=CATEGORIAS)


@app.route('/deletar/<int:id>', methods=['POST'])
def deletar(id):
    with get_db() as conn:
        bebida = conn.execute('SELECT nome FROM bebidas WHERE id = ?', (id,)).fetchone()
        if bebida:
            conn.execute('DELETE FROM bebidas WHERE id = ?', (id,))
            conn.commit()
            flash(f'"{bebida["nome"]}" removida com sucesso.', 'success')
        else:
            flash('Bebida não encontrada.', 'danger')
    return redirect(url_for('index'))


@app.route('/relatorio')
def relatorio():
    today = date.today().isoformat()

    with get_db() as conn:
        registros_hoje = conn.execute(
            "SELECT * FROM bebidas WHERE DATE(data_registro) = ? ORDER BY categoria, nome",
            (today,)
        ).fetchall()

        vencendo_breve = conn.execute(
            """SELECT *, JULIANDAY(validade) - JULIANDAY('now') AS dias_restantes
               FROM bebidas
               WHERE validade BETWEEN DATE('now') AND DATE('now', '+30 days')
               ORDER BY validade ASC""",
        ).fetchall()

        vencidos = conn.execute(
            """SELECT *, JULIANDAY(validade) - JULIANDAY('now') AS dias_restantes
               FROM bebidas
               WHERE validade < DATE('now')
               ORDER BY validade ASC"""
        ).fetchall()

        por_categoria = conn.execute(
            """SELECT categoria,
                      COUNT(*) AS qtd_produtos,
                      SUM(quantidade) AS qtd_total,
                      SUM(quantidade * valor) AS valor_total
               FROM bebidas
               GROUP BY categoria
               ORDER BY qtd_total DESC"""
        ).fetchall()

        totais = conn.execute(
            "SELECT COUNT(*) AS produtos, SUM(quantidade) AS unidades, SUM(quantidade * valor) AS valor_total FROM bebidas"
        ).fetchone()

    return render_template('relatorio.html',
                           registros_hoje=registros_hoje,
                           vencendo_breve=vencendo_breve,
                           vencidos=vencidos,
                           por_categoria=por_categoria,
                           totais=totais,
                           today=today)


@app.route('/relatorio/exportar')
def exportar_csv():
    today = date.today().isoformat()

    with get_db() as conn:
        registros = conn.execute(
            "SELECT * FROM bebidas WHERE DATE(data_registro) = ? ORDER BY categoria, nome",
            (today,)
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nome', 'Categoria', 'Validade', 'Quantidade', 'Valor Unit.', 'Valor Total', 'Data de Registro'])
    for r in registros:
        writer.writerow([r['id'], r['nome'], r['categoria'],
                         r['validade'], r['quantidade'],
                         f"{r['valor']:.2f}", f"{r['quantidade'] * r['valor']:.2f}",
                         r['data_registro']])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'relatorio_{today}.csv'
    )


# ── Importação via PDF ──────────────────────────────────────────────────────

# Mapeamento prefixo → categoria (ordem importa: mais específico primeiro)
_PREFIXOS = [
    ('BEB KOMBUCHA',   'Chá / Kombucha'),
    ('KOMBUCHA',       'Chá / Kombucha'),
    ('KIT CERV',       'Cerveja'),
    ('CERV ',          'Cerveja'),
    ('VINHO',          'Vinho / Espumante'),
    ('ESPUM',          'Vinho / Espumante'),
    ('CHAMP',          'Vinho / Espumante'),
    ('FRISANTE',       'Vinho / Espumante'),
    ('HIDROMEL',       'Vinho / Espumante'),
    ('REFRIG',         'Refrigerante'),
    ('AGUA MIN',       'Água'),
    ('AGUA TONICA',    'Água'),
    ('AGUA GASEIF',    'Água'),
    ('AGUA COCO',      'Água'),
    ('AGUA NAT',       'Água'),
    ('AGUA ROSA',      'Água'),
    ('AGUA ',          'Água'),
    ('SUCO',           'Suco'),
    ('LIMONADA',       'Suco'),
    ('ENERG ',         'Energético / Isotônico'),
    ('ISOT ',          'Energético / Isotônico'),
    ('GIN ',           'Destilados (Whisky, Vodka, Gin, Rum)'),
    ('VODKA',          'Destilados (Whisky, Vodka, Gin, Rum)'),
    ('WHISKY',         'Destilados (Whisky, Vodka, Gin, Rum)'),
    ('TEQUILA',        'Destilados (Whisky, Vodka, Gin, Rum)'),
    ('RUM ',           'Destilados (Whisky, Vodka, Gin, Rum)'),
    ('CONHAQUE',       'Destilados (Whisky, Vodka, Gin, Rum)'),
    ('AGUARD',         'Destilados (Whisky, Vodka, Gin, Rum)'),
    ('LICOR',          'Licor / Aperitivo'),
    ('APERIT',         'Licor / Aperitivo'),
    ('VERMUT',         'Licor / Aperitivo'),
    ('XAROPE',         'Licor / Aperitivo'),
    ('MARTINI',        'Licor / Aperitivo'),
    ('CACHACA',        'Cachaça'),
    ('BEB MISTA',      'Bebida Mista'),
    ('BEB ',           'Bebida Mista'),
    ('ICE ',           'Bebida Mista'),
    ('SIDRA',          'Bebida Mista'),
    ('SUPLEM',         'Bebida Mista'),
    ('CHA ',           'Chá / Kombucha'),
]


def infer_category(nome):
    """Infere categoria a partir do prefixo do nome do produto."""
    n = nome.upper()
    for prefix, cat in _PREFIXOS:
        if n.startswith(prefix):
            return cat
    return 'Outros'


def _parse_qty_br(s):
    """Converte número em formato brasileiro ('1.716,000') para int."""
    return int(float(s.replace('.', '').replace(',', '.')))


def detect_pdf_format(path):
    """Detecta o formato do PDF: 'validade', 'abc' ou 'desconhecido'."""
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ''
    if 'Relatório de Estoque por Data de Validade' in text:
        return 'validade'
    if 'Análise ABC do Estoque' in text:
        return 'abc'
    return 'desconhecido'


def parse_pdf_validade(path):
    """
    PDF 1 — Relatório de Estoque por Data de Validade (TOTVS).
    Cada lote (data diferente) gera um registro separado.
    Retorna lista de dicts: {nome, categoria, validade, quantidade}
    """
    _SKIP = {'Data de Validade', 'Relatório de Estoque', 'TOTVS',
             'Estq. por Validade', 'P MORADA', 'P ADRIANO', 'MERCANTIL'}
    produtos = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            current_nome = None

            for line in text.split('\n'):
                line = line.strip()
                if not line or any(s in line for s in _SKIP):
                    continue

                # "Produto 59943 CERV HB GF 500ML WEISSBIER T5,1%"
                m = re.match(r'^Produto\s+\d+\s+(.+)$', line)
                if m:
                    current_nome = m.group(1).strip()
                    continue

                if line.startswith('Estoque Disponível'):
                    continue

                # "01/09/2026 60,000" ou "01/09/2026 1.716,000"
                if current_nome:
                    m = re.match(r'^(\d{2}/\d{2}/\d{4})\s+([\d.,]+)$', line)
                    if m:
                        d, mo, y = m.group(1).split('/')
                        try:
                            qt = _parse_qty_br(m.group(2))
                        except ValueError:
                            continue
                        if qt > 0:
                            produtos.append({
                                'nome':       current_nome,
                                'categoria':  infer_category(current_nome),
                                'validade':   f'{y}-{mo}-{d}',
                                'quantidade': qt,
                                'valor':      0.0,
                            })
    return produtos


def parse_pdf_abc(path, validade_padrao):
    """
    PDF 2 — Análise ABC do Estoque (TOTVS).
    Sem datas de validade; usa validade_padrao (YYYY-MM-DD) para todos.
    Retorna lista de dicts: {nome, categoria, validade, quantidade}
    """
    _SKIP = {'Análise ABC', 'Divisão:', 'Período:', 'Empresas:', 'Detalhamentos:',
             'Filtros:', 'Categorias', 'Produtos Ativos', 'Quantidade Total',
             'Restrito', 'Filtrados', 'Tipos de', 'Imprimindo', 'TOTVS',
             'MERCANTIL', 'Produto Quantidade', 'Dias Sem', 'em Estoque',
             'Preço Vda', 'Lucrat.', 'Lucratividade', 'Qtd. Pend.',
             'Ped.Compra', 'Dias Ult.', 'Código', 'TOTAL:'}

    # Linha de dados: CÓDIGO  NOME  dias_sem_venda  qtd_estoque(X,XXX)  preço(X,XX)  ...
    # qtd tem 3 casas decimais; preço tem 2 casas decimais (ambos formato BR)
    _ROW = re.compile(
        r'^(\d{2,6})\s+'             # código do produto
        r'(.+?)\s+'                  # nome (não-guloso)
        r'\d+\s+'                    # dias sem vendas (inteiro)
        r'([\d.]+,\d{3})'           # qtd em estoque (3 decimais BR)
        r'(?:\s+([\d.]+,\d{2}))?'   # preço unitário (2 decimais BR, opcional)
    )

    vistos = set()   # deduplica por código (produto aparece em várias páginas)
    produtos = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for line in text.split('\n'):
                line = line.strip()
                if not line or any(s in line for s in _SKIP):
                    continue

                m = _ROW.match(line)
                if not m:
                    continue

                code, nome, qty_str = m.group(1), m.group(2).strip(), m.group(3)
                preco_str = m.group(4)

                if not nome or code in vistos:
                    continue
                vistos.add(code)

                try:
                    qt = _parse_qty_br(qty_str)
                except ValueError:
                    continue

                if qt <= 0:
                    continue

                try:
                    valor = float(preco_str.replace('.', '').replace(',', '.')) if preco_str else 0.0
                except ValueError:
                    valor = 0.0

                produtos.append({
                    'nome':       nome,
                    'categoria':  infer_category(nome),
                    'validade':   validade_padrao,
                    'quantidade': qt,
                    'valor':      valor,
                })

    return produtos


@app.route('/importar', methods=['GET', 'POST'])
def importar():
    if request.method == 'POST':
        action = request.form.get('action')

        # ── Passo 1: recebe o arquivo, parseia, mostra preview ──
        if action == 'upload':
            arquivo = request.files.get('arquivo')
            if not arquivo or not arquivo.filename.lower().endswith('.pdf'):
                flash('Envie um arquivo .pdf válido.', 'danger')
                return redirect(url_for('importar'))

            validade_padrao = request.form.get('validade_padrao', '').strip()

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            try:
                arquivo.save(tmp.name)
                tmp.close()

                fmt = detect_pdf_format(tmp.name)

                if fmt == 'validade':
                    produtos = parse_pdf_validade(tmp.name)
                    fmt_label = 'Relatório de Estoque por Data de Validade'
                elif fmt == 'abc':
                    if not validade_padrao:
                        flash('Para o relatório ABC, informe uma data de validade padrão.', 'warning')
                        return redirect(url_for('importar'))
                    produtos = parse_pdf_abc(tmp.name, validade_padrao)
                    fmt_label = 'Análise ABC do Estoque'
                else:
                    flash('Formato de PDF não reconhecido. Use o Relatório de Validade ou a Análise ABC.', 'danger')
                    return redirect(url_for('importar'))

            except Exception as e:
                flash(f'Erro ao processar o PDF: {e}', 'danger')
                return redirect(url_for('importar'))
            finally:
                os.unlink(tmp.name)

            if not produtos:
                flash('Nenhum produto identificado. Verifique o arquivo.', 'warning')
                return redirect(url_for('importar'))

            with get_db() as conn:
                existentes = {
                    (r['nome'], r['validade'])
                    for r in conn.execute('SELECT nome, validade FROM bebidas').fetchall()
                }

            for p in produtos:
                p['existente'] = (p['nome'], p['validade']) in existentes

            duplicatas = sum(1 for p in produtos if p['existente'])

            return render_template('importar.html',
                                   produtos=produtos,
                                   preview=True,
                                   fmt_label=fmt_label,
                                   duplicatas=duplicatas)

        # ── Passo 2: usuário confirmou, insere no banco ──
        elif action == 'confirmar':
            try:
                produtos = json.loads(request.form.get('produtos_json', '[]'))
            except Exception:
                flash('Erro ao processar dados. Tente novamente.', 'danger')
                return redirect(url_for('importar'))

            indices = {int(i) for i in request.form.getlist('selecionado')}
            inseridos = 0
            sobrescritos = 0

            with get_db() as conn:
                for i, p in enumerate(produtos):
                    if i not in indices:
                        continue
                    existente = conn.execute(
                        'SELECT id FROM bebidas WHERE nome = ? AND validade = ?',
                        (p['nome'], p['validade'])
                    ).fetchone()
                    if existente:
                        conn.execute(
                            'UPDATE bebidas SET categoria=?, quantidade=?, valor=? WHERE id=?',
                            (p['categoria'], p['quantidade'], p.get('valor', 0.0), existente['id'])
                        )
                        sobrescritos += 1
                    else:
                        conn.execute(
                            'INSERT INTO bebidas (nome, categoria, validade, quantidade, valor) '
                            'VALUES (?, ?, ?, ?, ?)',
                            (p['nome'], p['categoria'], p['validade'], p['quantidade'], p.get('valor', 0.0))
                        )
                        inseridos += 1
                conn.commit()

            partes = []
            if inseridos:
                partes.append(f'{inseridos} inserida(s)')
            if sobrescritos:
                partes.append(f'{sobrescritos} sobrescrita(s)')
            if partes:
                flash(f'{" e ".join(partes)} com sucesso!', 'success')
            else:
                flash('Nenhum item foi importado.', 'warning')
            return redirect(url_for('index'))

    return render_template('importar.html', preview=False, produtos=[])


@app.context_processor
def inject_now():
    return {'now': datetime.now()}


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
