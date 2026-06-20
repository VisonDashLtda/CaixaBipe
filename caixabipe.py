import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import datetime

# Configuração da página
st.set_page_config(page_title="Vison Controle & Caixa", layout="wide", initial_sidebar_state="expanded")

# Conexão com o banco de dados Neon via Secrets
def obter_conexao():
    try:
        url_banco = st.secrets["postgres"]["url"]
        return psycopg2.connect(url_banco, cursor_factory=RealDictCursor)
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

# Inicializar o banco de dados e tabelas
conn = obter_conexao()
if conn:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(255) NOT NULL,
            categoria VARCHAR(100),
            quantidade_atual INT NOT NULL DEFAULT 0,
            estoque_minimo INT NOT NULL DEFAULT 5,
            preco_custo DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            preco_venda DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            codigo_barras VARCHAR(50) UNIQUE
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id SERIAL PRIMARY KEY,
            produto_id INT REFERENCES produtos(id) ON DELETE CASCADE,
            tipo VARCHAR(10) CHECK (tipo IN ('ENTRADA', 'SAÍDA')),
            quantidade INT NOT NULL,
            data_movimentacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()

# Sistema de Login Simples
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False
    st.session_state['perfil'] = None

if not st.session_state['autenticado']:
    st.title("🔑 Acesso ao Sistema - Vison")
    usuario = st.text_input("Usuário:")
    senha = st.text_input("Senha:", type="password")
    
    if st.button("Entrar"):
        if usuario == "admin" and senha == "vison123":
            st.session_state['autenticado'] = True
            st.session_state['perfil'] = "ADMIN"
            st.rerun()
        elif usuario == "caixa" and senha == "vison456":
            st.session_state['autenticado'] = True
            st.session_state['perfil'] = "FUNCIONARIO"
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")
else:
    # Menu Lateral
    st.sidebar.title("Navegação")
    st.sidebar.write(f"👤 Conectado como: **{st.session_state['perfil']}**")
    
    if st.session_state['perfil'] == "ADMIN":
        paginas = ["Dashboard de Vendas", "Cadastrar Novo Produto", "Entrada / Saída (Fluxo)", "Histórico de Auditoria"]
    else:
        paginas = ["Entrada / Saída (Fluxo)"]
        
    tela = st.sidebar.radio("Selecione a Tela:", paginas)
    
    if st.sidebar.button("🔴 Sair do Sistema"):
        st.session_state['autenticado'] = False
        st.session_state['perfil'] = None
        st.rerun()

    # --- TELA 1: DASHBOARD ---
    if tela == "Dashboard de Vendas":
        st.title("📈 Dashboard de Vendas e Controle")
        conn = obter_conexao()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, codigo_barras, nome, categoria, quantidade_atual, estoque_minimo, preco_venda FROM produtos ORDER BY nome ASC")
            produtos = cursor.fetchall()
            
            if produtos:
                st.subheader("📦 Itens em Estoque")
                for prod in produtos:
                    cor = "green" if prod['quantidade_atual'] > prod['estoque_minimo'] else "red"
                    st.markdown(f"**[{prod['codigo_barras'] or 'Sem Código'}]** {prod['nome']} - Categoria: {prod['categoria']} | Estoque: :{cor}[{prod['quantidade_atual']}/{prod['estoque_minimo']}] | Preço: R${prod['preco_venda']:.2f}")
            else:
                st.info("Nenhum produto cadastrado ainda.")
            cursor.close()
            conn.close()

    # --- TELA 2: CADASTRAR PRODUTO ---
    elif tela == "Cadastrar Novo Produto":
        st.title("📦 Cadastrar Novo Produto")
        
        with st.form("form_cadastro", clear_on_submit=True):
            st.info("💡 Clique no campo 'Código de Barras' abaixo e bipe o produto com o leitor USB")
            txt_codigo = st.text_input("Código de Barras (Bipe com o Leitor):", key="cadastro_barcode")
            txt_nome = st.text_input("Nome do Produto:")
            txt_cat = st.text_input("Categoria:")
            num_qtd = st.number_input("Quantidade Inicial em Estoque:", min_value=0, step=1)
            num_min = st.number_input("Aviso de Estoque Mínimo:", min_value=1, value=5, step=1)
            num_custo = st.number_input("Preço de Custo (R$):", min_value=0.0, step=0.50)
            num_venda = st.number_input("Preço de Venda (R$):", min_value=0.0, step=0.50)
            
            btn_salvar = st.form_submit_button("Salvar Produto")
            
            if btn_salvar:
                if txt_nome and txt_codigo:
                    conn = obter_conexao()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO produtos (nome, categoria, quantidade_atual, estoque_minimo, preco_custo, preco_venda, codigo_barras)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (txt_nome, txt_cat, num_qtd, num_min, num_custo, num_venda, txt_codigo))
                            conn.commit()
                            st.success(f"✔️ '{txt_nome}' cadastrado com sucesso com o código {txt_codigo}!")
                        except Exception as err:
                            st.error(f"Erro ao salvar: Código de barras já cadastrado em outro produto.")
                        finally:
                            cursor.close()
                            conn.close()
                else:
                    st.warning("Preencha o Nome e o Código de Barras do produto.")

    # --- TELA 3: ENTRADA / SAÍDA AUTOMÁTICA (LEITOR) ---
    elif tela == "Entrada / Saída (Fluxo)":
        st.title("🚚 Entrada / Saída (Fluxo de Caixa)")
        
        # Campo focado para o leitor de código de barras
        st.markdown("### ⚡ POSICIONE O CURSOR NO CAMPO ABAIXO E BIPE O PRODUTO:")
        codigo_bipado = st.text_input("", value="", key="txt_leitor", autocomplete="off")
        
        if codigo_bipado:
            conn = obter_conexao()
            if conn:
                cursor = conn.cursor()
                # Busca o produto pelo código de barras exato
                cursor.execute("SELECT id, nome, quantidade_atual FROM produtos WHERE codigo_barras = %s", (codigo_bipado,))
                prod = cursor.fetchone()
                
                if prod:
                    if prod['quantidade_atual'] > 0:
                        # Realiza a baixa automática (-1 un.)
                        nova_qtd = prod['quantidade_atual'] - 1
                        cursor.execute("UPDATE produtos SET quantidade_atual = %s WHERE id = %s", (nova_qtd, prod['id']))
                        cursor.execute("INSERT INTO movimentacoes (produto_id, tipo, quantidade) VALUES (%s, 'SAÍDA', 1)", (prod['id'],))
                        conn.commit()
                        st.success(f"🛒 Baixa Efetuada: **{prod['nome']}** (-1 unidade). Restam {nova_qtd} no estoque.")
                    else:
                        st.error(f"❌ Estoque esgotado para o produto: **{prod['nome']}**.")
                else:
                    st.warning(f"⚠️ Código de barras '{codigo_bipado}' não encontrado no sistema. Cadastre-o primeiro.")
                
                cursor.close()
                conn.close()
                # Força a limpeza do campo de texto para o próximo bipe
                st.markdown("<script>document.getElementById('txt_leitor').value = '';</script>", unsafe_allow_html=True)

    # --- TELA 4: HISTÓRICO DE AUDITORIA ---
    elif tela == "Histórico de Auditoria":
        st.title("📋 Histórico de Auditoria e Movimentações")
        conn = obter_conexao()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id, p.nome, p.codigo_barras, m.tipo, m.quantidade, m.data_movimentacao 
                FROM movimentacoes m
                JOIN produtos p ON m.produto_id = p.id
                ORDER BY m.data_movimentacao DESC LIMIT 50
            """)
            historico = cursor.fetchall()
            
            if historico:
                for reg in historico:
                    data_f = reg['data_movimentacao'].strftime('%d/%m/%Y %H:%M:%S')
                    tipo_cor = "🔴" if reg['tipo'] == "SAÍDA" else "🟢"
                    st.write(f"{tipo_cor} **[{data_f}]** {reg['nome']} ({reg['codigo_barras']}) | Tipo: {reg['tipo']} | Qtd: {reg['quantidade']} un.")
            else:
                st.info("Nenhuma movimentação realizada até o momento.")
            cursor.close()
            conn.close()