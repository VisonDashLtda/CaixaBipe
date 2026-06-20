import streamlit as st
import pandas as pd
import psycopg2

def conectar_banco():
    # String de conexão segura com o Neon DB
    url_conexao = "postgresql://neondb_owner:npg_4fbN3iTzXmre@ep-plain-snow-atggseac.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require"
    return psycopg2.connect(dsn=url_conexao)

st.set_page_config(page_title="Portal de Estoque", layout="wide")

# =========================================================
# SISTEMA DE AUTENTICAÇÃO (TELA DE LOGIN)
# =========================================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "nivel_usuario" not in st.session_state:
    st.session_state["nivel_usuario"] = None

def realizar_login(usuario, senha):
    if usuario == "admin" and senha == "vison123":
        st.session_state["autenticado"] = True
        st.session_state["nivel_usuario"] = "admin"
        st.success("Login de Administrador realizado com sucesso!")
        st.rerun()
    elif usuario == "funcionario" and senha == "senha123":
        st.session_state["autenticado"] = True
        st.session_state["nivel_usuario"] = "funcionario"
        st.success("Login de Funcionário realizado com sucesso!")
        st.rerun()
    else:
        st.error("Usuário ou senha incorretos.")

if not st.session_state["autenticado"]:
    st.title("🔒 Acesso ao Sistema de Estoque")
    st.markdown("Por favor, insira suas credenciais para gerenciar o estoque.")
    
    with st.form("form_login"):
        campo_usuario = st.text_input("Usuário")
        campo_senha = st.text_input("Senha", type="password")
        botao_entrar = st.form_submit_button("Entrar no Sistema", use_container_width=True)
        
        if botao_entrar:
            realizar_login(campo_usuario, campo_senha)

else:
    if st.session_state["nivel_usuario"] == "admin":
        opcoes_menu = [
            "📈 Dashboard de Vendas", 
            "📦 Cadastrar Novo Produto", 
            "🚚 Entrada / Saída (Fluxo)", 
            "📅 Histórico de Auditoria"
        ]
    else:
        opcoes_menu = [
            "📈 Dashboard de Vendas", 
            "🚚 Entrada / Saída (Fluxo)"
        ]

    st.sidebar.title("Navegação")
    st.sidebar.write(f"👤 Conectado como: **{st.session_state['nivel_usuario'].upper()}**")
    menu = st.sidebar.radio("Selecione a Tela:", opcoes_menu)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🔴 Sair do Sistema", use_container_width=True):
        st.session_state["autenticado"] = False
        st.session_state["nivel_usuario"] = None
        st.rerun()

    # =========================================================
    # TELA 1: DASHBOARD DE VENDAS
    # =========================================================
    if menu == "📈 Dashboard de Vendas":
        st.title("📈 Dashboard de Vendas e Controle")
        
        try:
            conn = conectar_banco()
            # Trocado "id" por "Código" para blindar o bug do formato SYLK no Excel
            query = '''SELECT id AS "Código", codigo_barras AS "Cód. Barras", nome AS "Produto", categoria AS "Categoria", quantidade_atual AS "Qtd Atual", estoque_minimo AS "Estoque Mínimo", preco_custo AS "Preço Custo", preco_venda AS "Preço Venda" FROM produtos'''
            df = pd.read_sql(query, conn)
            
            query_vendas = '''
                SELECT m.quantidade, p.preco_custo, p.preco_venda 
                FROM movimentacoes m
                INNER JOIN produtos p ON m.produto_id = p.id
                WHERE m.tipo = 'SAÍDA'
            '''
            df_vendas = pd.read_sql(query_vendas, conn)
            conn.close()
        except Exception as e:
            st.error(f"Erro ao conectar ao banco de dados: {e}")
            df = pd.DataFrame()
            df_vendas = pd.DataFrame()

        if not df.empty:
            capital_investido = float((df['Qtd Atual'] * df['Preço Custo']).sum())
            
            if not df_vendas.empty:
                faturamento_total = float((df_vendas['quantidade'] * df_vendas['preco_venda']).sum())
                custo_total_vendido = float((df_vendas['quantidade'] * df_vendas['preco_custo']).sum())
                lucro_real = faturamento_total - custo_total_vendido
            else:
                faturamento_total = 0.0
                lucro_real = 0.0

            st.subheader("💰 Resumo Financeiro e Operacional")
            col_fat, col_lucro, col_inv, col_alertas = st.columns(4)
            
            # Formatação corrigida e simplificada para evitar a tela vermelha (ValueError)
            col_fat.metric("Faturamento Total", f"R$ {faturamento_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            col_lucro.metric("Lucro Líquido Real", f"R$ {lucro_real:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            col_inv.metric("Capital em Estoque", f"R$ {capital_investido:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            produtos_criticos = df[df['Qtd Atual'] <= df['Estoque Mínimo']]
            total_criticos = len(produtos_criticos)
            col_alertas.metric("Produtos em Alerta", total_criticos)
            
            if total_criticos > 0:
                st.error(f"⚠️ **Atenção:** Você tem {total_criticos} produto(s) abaixo ou no limite do estoque mínimo!")
                with st.expander("🔎 Ver lista de compras necessária"):
                    st.dataframe(produtos_criticos[['Produto', 'Qtd Atual', 'Estoque Mínimo']], hide_index=True)
            else:
                st.success("✅ Todos os produtos estão com níveis de estoque saudáveis!")

            st.markdown("---")
            st.subheader("📋 Todos os Produtos em Estoque")
            
            col_busca, col_filtro_cat = st.columns(2)
            with col_busca:
                busca_nome = st.text_input("🔍 Buscar produto pelo nome ou código de barras:", placeholder="Digite o nome ou bipe o código...")
            
            with col_filtro_cat:
                lista_categorias = ["Todas"] + sorted(df["Categoria"].dropna().unique().tolist())
                categoria_selecionada = st.selectbox("📂 Filtrar por Categoria:", lista_categorias)
            
            df_filtrado = df.copy()
            if busca_nome:
                df_filtrado = df_filtrado[
                    df_filtrado["Produto"].str.contains(busca_nome, case=False, na=False) | 
                    df_filtrado["Cód. Barras"].str.contains(busca_nome, case=False, na=False)
                ]
            if categoria_selecionada != "Todas":
                df_filtrado = df_filtrado[df_filtrado["Categoria"] == categoria_selecionada]

            # GERAÇÃO DO CSV SEGURO DE DOWNLOAD (Sem usar openpyxl ou xlsxwriter)
            col_vazia, col_botao = st.columns([4, 1])
            with col_botao:
                csv_dados = df_filtrado.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button(
                    label="📥 Baixar Dados (Excel / CSV)",
                    data=csv_dados,
                    file_name="relatorio_estoque_atual.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            def colorir_criticos(row):
                return ['background-color: #ffcccc' if row['Qtd Atual'] <= row['Estoque Mínimo'] else '' for _ in row]
                
            df_formatado = df_filtrado.style.format({
                'Preço Custo': 'R$ {:.2f}',
                'Preço Venda': 'R$ {:.2f}'
            }).apply(colorir_criticos, axis=1)
                
            st.dataframe(df_formatado, use_container_width=True, hide_index=True)

    # =========================================================
    # TELA 2: CADASTRAR NOVO PRODUTO (RESTRITA: ADMIN)
    # =========================================================
    elif menu == "📦 Cadastrar Novo Produto" and st.session_state["nivel_usuario"] == "admin":
        st.title("📦 Cadastro de Novos Produtos")
        
        with st.form("form_cadastro"):
            nome = st.text_input("Nome do Produto")
            categoria = st.text_input("Categoria")
            codigo_barras = st.text_input("Código de Barras (Opcional - Bipe o produto aqui)")
            
            quantidade_inicial = st.number_input("Quantidade Inicial em Estoque", min_value=0, step=1)
            estoque_minimo = st.number_input("Estoque Mínimo (Alerta)", min_value=1, value=5, step=1)
            preco_custo = st.number_input("Preço de Custo (R$)", min_value=0.0, format="%.2f")
            preco_venda = st.number_input("Preço de Venda (R$)", min_value=0.0, format="%.2f")
            
            botao_cadastrar = st.form_submit_button("Salvar Produto")
            
            if botao_cadastrar:
                if nome:
                    try:
                        conn = conectar_banco()
                        cursor = conn.cursor()
                        sql = """INSERT INTO produtos (nome, categoria, quantidade_atual, estoque_minimo, preco_custo, preco_venda, codigo_barras) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                        valores = (nome, categoria, quantidade_inicial, estoque_minimo, preco_custo, preco_venda, codigo_barras if codigo_barras else None)
                        cursor.execute(sql, valores)
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success(f"Produto '{nome}' cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar no banco (Verifique se o código de barras já existe): {e}")
                else:
                    st.warning("O nome do produto é obrigatório.")

    # =========================================================
    # TELA 3: ENTRADA / SAÍDA (FLUXO AUTOMÁTICO COM LEITOR)
    # =========================================================
    elif menu == "🚚 Entrada / Saída (Fluxo)":
        st.title("🚚 Frente de Caixa - Baixa por Código de Barras")
        st.markdown("Deixe o cursor piscando no campo abaixo e passe o produto no leitor para dar baixa automática.")

        codigo_bipado = st.text_input("⚡ BIPIE O CÓDIGO DE BARRAS AQUI:", value="", key="txt_leitor", autocomplete="off")

        if codigo_bipado:
            try:
                conn = conectar_banco()
                cursor = conn.cursor()
                cursor.execute("SELECT id, nome, quantidade_atual FROM produtos WHERE codigo_barras = %s", (codigo_bipado,))
                produto = cursor.fetchone()
                
                if produto:
                    id_p, nome_p, qtd_p = produto
                    if qtd_p >= 1:
                        cursor.execute("INSERT INTO movimentacoes (produto_id, tipo, quantidade) VALUES (%s, 'SAÍDA', 1)", (id_p,))
                        cursor.execute("UPDATE produtos SET quantidade_atual = quantidade_atual - 1 WHERE id = %s", (id_p,))
                        conn.commit()
                        st.success(f"🛒 Baixa efetuada: **{nome_p}** (-1 un.) | Novo Estoque: {qtd_p - 1}")
                    else:
                        st.error(f"❌ Estoque esgotado para o produto: {nome_p}!")
                else:
                    st.warning(f"⚠️ Código de barras '{codigo_bipado}' não encontrado.")
                cursor.close()
                conn.close()
            except Exception as e:
                st.error(f"Erro ao processar o código: {e}")

        st.markdown("---")
        with st.expander("⌨️ Operação Manual (Sem Leitor)"):
            try:
                conn = conectar_banco()
                df_produtos = pd.read_sql("SELECT id, nome, quantidade_atual FROM produtos", conn)
                conn.close()
            except:
                df_produtos = pd.DataFrame()
                
            if not df_produtos.empty:
                lista_produtos = [f"{row['id']} - {row['nome']} (Atual: {row['quantidade_atual']})" for _, row in df_produtos.iterrows()]
                with st.form("form_movimentacao_manual"):
                    produto_selecionado = st.selectbox("Escolha o Produto:", lista_produtos)
                    tipo_movimento = st.selectbox("Tipo de Operação:", ["ENTRADA", "SAÍDA"])
                    qtd_movimentada = st.number_input("Quantidade:", min_value=1, step=1)
                    botao_movimentar = st.form_submit_button("Confirmar Manualmente")
                    
                    if botao_movimentar:
                        id_produto = int(produto_selecionado.split(" - ")[0])
                        qtd_atual = int(df_produtos[df_produtos['id'] == id_produto]['quantidade_atual'].values[0])
                        if tipo_movimento == "SAÍDA" and qtd_movimentada > qtd_atual:
                            st.error("Erro: Quantidade indisponível!")
                        else:
                            try:
                                conn = conectar_banco()
                                cursor = conn.cursor()
                                cursor.execute("INSERT INTO movimentacoes (produto_id, tipo, quantidade) VALUES (%s, %s, %s)", (id_produto, tipo_movimento, qtd_movimentada))
                                if tipo_movimento == "ENTRADA":
                                    cursor.execute("UPDATE produtos SET quantidade_atual = quantidade_atual + %s WHERE id = %s", (qtd_movimentada, id_produto))
                                else:
                                    cursor.execute("UPDATE produtos SET quantidade_atual = quantidade_atual - %s WHERE id = %s", (qtd_movimentada, id_produto))
                                conn.commit()
                                cursor.close()
                                conn.close()
                                st.success("Estoque atualizado com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")

    # =========================================================
    # TELA 4: HISTÓRICO DE AUDITORIA (RESTRITA: ADMIN)
    # =========================================================
    elif menu == "📅 Histórico de Auditoria" and st.session_state["nivel_usuario"] == "admin":
        st.title("📅 Histórico e Auditoria de Estoque")
        
        try:
            conn = conectar_banco()
            query_hist = """
                SELECT m.id AS "Cód. Mov", p.nome AS "Produto", m.tipo AS "Operação", 
                       m.quantidade AS "Quantidade", 
                       TO_CHAR(m.data_movimentacao, 'DD/MM/YYYY HH24:MI') AS "Data/Hora"
                FROM movimentacoes m
                INNER JOIN produtos p ON m.produto_id = p.id
                ORDER BY m.data_movimentacao DESC
            """
            df_historico = pd.read_sql(query_hist, conn)
            conn.close()
        except Exception as e:
            st.error(f"Erro ao carregar histórico: {e}")
            df_historico = pd.DataFrame()
            
        if not df_historico.empty:
            csv_hist = df_historico.to_csv(index=False, sep=';', encoding='utf-8-sig')
            st.download_button(
                label="📥 Exportar Histórico para Excel",
                data=csv_hist,
                file_name="historico_movimentacoes.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.dataframe(df_historico, use_container_width=True, hide_index=True)