# Gestor de Bebidas

Controle de estoque de bebidas com importação de PDFs do TOTVS.

## Requisitos

- Python 3.10+

## Instalação

```bash
# Clone o repositório
git clone git@github.com:SCROLLUCK/patio-manager.git
cd patio-manager

# Crie e ative o ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# Instale as dependências
pip install -r requirements.txt
```

## Rodando

```bash
flask run
```

Acesse [http://localhost:5000](http://localhost:5000).

O banco de dados (`bebidas.db`) é criado automaticamente na primeira execução.

## Funcionalidades

- **Estoque** — listagem com busca, filtro por categoria e ordenação por validade, quantidade, valor e data de registro
- **Cadastrar / Editar** — nome, categoria, validade, quantidade e valor unitário
- **Relatório** — resumo diário, produtos vencidos, vencendo em 30 dias e totais por categoria
- **Importar PDF** — suporta dois formatos do TOTVS:
  - *Relatório de Estoque por Data de Validade* — importa nome, validade e quantidade por lote
  - *Análise ABC do Estoque* — importa nome, quantidade e preço unitário (requer data de validade padrão)
- **Exportar CSV** — exporta os registros do dia com valor unitário e total
