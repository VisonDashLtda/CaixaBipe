import streamlit as st
import pandas as pd
import psycopg2  # <-- Conexão com o Postgres/Neon

def conectar_banco():
    # Sua string de conexão com o banco Neon
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

# Se NÃO está logado, mostra apenas a tela de login
if not st.session_state["autenticado"]:
    st.title("🔒 Acesso ao Sistema de Estoque")
    st.markdown("Por favor, insira suas credenciais para gerenciar o estoque da empresa.")
    
    with st.form("form_login"):
        campo_usuario = st.text_input("Usuário")
        campo_senha = st.text_input("Senha", type="password")
        botao_entrar = st.form_submit_button("Entrar no Sistema", use_container_width=True)
        
        if botao_entrar:
            realizar_login(campo_usuario, campo_senha)

# Se JÁ está logado, libera o sistema com base nas permissões
else:
    # --- DEFINE AS OPÇÕES DE MENU CONFORME O NÍVEL ---
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

    # --- MENU LATERAL DE NAVEGAÇÃO ---
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
            capital_investido = (df['Qtd Atual'] * df['Preço Custo']).sum()
            
            if not df_vendas.empty:
                faturamento_total = (df_vendas['quantidade'] * df_vendas['preco_venda']).sum()
                custo_total_vendido = (df_vendas['quantidade'] * df_vendas['preco_custo']).sum()
                lucro_real = faturamento_total - custo_total_vendido
            else:
                faturamento_total = 0.0
                lucro_real = 0.0

            st.subheader("💰 Resumo Financeiro e Operacional")
            col_fat, col_lucro, col_inv, col_alertas = st.columns(4)
            
            col_fat.metric("Faturamento Total", f"R$ {faturamento_total:,.2f}")
            col_lucro.metric("Lucro Líquido Real", f"R$ {lucro_real:,.2f}")
            col_inv.metric("Capital em Estoque", f"R$ {capital_investido:,.2f}")
            
            produtos_criticos = df[df['Qtd Atual'] <= df['Estoque Mínimo']]
            total_criticos = len(produtos_criticos)
            col_alertas.metric("Produtos em Alerta", total_criticos, delta=-total_criticos, delta_color="inverse" if total_criticos > 0 else "normal")
            
            if total_criticos > 0:
                st.error(f"⚠️ **Atenção:** Você tem {total_criticos} produto(s) abaixo ou no limite do estoque mínimo!")
                with st.expander("🔎 Ver lista de compras necessária"):
                    st.dataframe(produtos_criticos[['Produto', 'Qtd Atual', 'Estoque Mínimo']], hide_index=True)
            else:
                st.success("✅ Todos os produtos estão com níveis de estoque saudáveis!")

            st.markdown("---")
            st.subheader("🔥 Top 5 Produtos Mais Vendidos")
            
            try:
                conn = conectar_banco()
                query_top5 = """
                    SELECT p.nome AS "Produto", SUM(m.quantidade) AS "Total Vendido"
                    FROM movimentacoes m
                    INNER JOIN produtos p ON m.produto_id = p.id
                    WHERE m.tipo = 'SAÍDA'
                    GROUP BY p.nome
                    ORDER BY "Total Vendido" DESC
                    LIMIT 5
                """
                df_top5 = pd.read_sql(query_top5, conn)
                conn.close()
                
                if not df_top5.empty:
                    st.bar_chart(data=df_top5, x="Produto", y="Total Vendido", color="#ff4b4b")
                else:
                    st.info("Ainda não há registros de saídas/vendas suficientes para gerar o gráfico.")
            except Exception as e:
                st.error(f"Erro ao gerar gráfico de vendas: {e}")
            
            # --- FILTROS INTELIGENTES E BUSCA ---
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
                # Permite buscar pelo nome OU pelo código de barras na barra de pesquisa superior
                df_filtrado = df_filtrado[
                    df_filtrado["Produto"].str.contains(busca_nome, case=False, na=False) | 
                    df_filtrado["Cód. Barras"].str.contains(busca_nome, case=False, na=False)
                ]
            if categoria_selecionada != "Todas":
                df_filtrado = df_filtrado[df_filtrado["Categoria"] == categoria_selecionada]

            col_vazia, col_botao = st.columns([4, 1])
            with col_botao:
                csv_dados = df_filtrado.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button(
                    label="📥 Baixar Dados Filtrados",
                    data=csv_dados,
                    file_name="relatorio_estoque_filtrado.csv",
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
            
            # NOVO CAMPO: Para você cadastrar o código usando o leitor
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
                        # Query atualizada com o campo codigo_barras
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

        # --- SEÇÃO DE REMOÇÃO ---
        st.markdown("---")
        st.subheader("🗑️ Remover Produto do Sistema")
        try:
            conn = conectar_banco()
            df_deletar = pd.read_sql("SELECT id, nome FROM produtos", conn)
            conn.close()
        except Exception as e:
            df_deletar = pd.DataFrame()

        if not df_deletar.empty:
            lista_deletar = [f"{row['id']} - {row['nome']}" for _, row in df_deletar.iterrows()]
            produto_para_deletar = st.selectbox("Selecione o produto que deseja excluir permanentemente:", lista_deletar)
            botao_deletar = st.button("🔴 Excluir Produto Definitivamente", use_container_width=True)
            
            if botao_deletar:
                id_deletar = int(produto_para_deletar.split(" - ")[0])
                nome_deletar = produto_para_deletar.split(" - ")[1]
                try:
                    conn = conectar_banco()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM movimentacoes WHERE produto_id = %s", (id_deletar,))
                    cursor.execute("DELETE FROM produtos WHERE id = %s", (id_deletar,))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success(f"Produto '{nome_deletar}' removido com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao deletar produto: {e}")

    # =========================================================
    # TELA 3: ENTRADA / SAÍDA (FLUXO AUTOMÁTICO COM LEITOR)
    # =========================================================
    elif menu == "🚚 Entrada / Saída (Fluxo)":
        st.title("🚚 Frente de Caixa - Baixa por Código de Barras")
        st.markdown("Deixe o cursor piscando no campo abaixo e passe o produto no leitor para dar baixa automática.")

        # Campo de texto principal que captura o "bip" do leitor
        # O argumento value="" e a limpeza pós-uso garantem velocidade
        codigo_bipado = st.text_input("⚡ BIPIE O CÓDIGO DE BARRAS AQUI:", value="", key="txt_leitor", autocomplete="off")

        # Se o leitor mandou dados e deu o "Enter" automático:
        if codigo_bipado:
            try:
                conn = conectar_banco()
                cursor = conn.cursor()
                
                # 1. Procura o produto correspondente ao código bipado
                cursor.execute("SELECT id, nome, quantidade_atual FROM produtos WHERE codigo_barras = %s", (codigo_bipado,))
                produto = cursor.fetchone()
                
                if produto:
                    id_p, nome_p, qtd_p = produto
                    
                    # Como é um caixa rápido de panificadora/loja, assume-se a SAÍDA de 1 unidade por padrão
                    if qtd_p >= 1:
                        # Registra na auditoria
                        cursor.execute("INSERT INTO movimentacoes (produto_id, tipo, quantidade) VALUES (%s, 'SAÍDA', 1)", (id_p,))
                        # Remove 1 do estoque atual
                        cursor.execute("UPDATE produtos SET quantidade_atual = quantidade_atual - 1 WHERE id = %s", (id_p,))
                        conn.commit()
                        st.success(f"🛒 Baixa efetuada: **{nome_p}** (-1 un.) | Novo Estoque: {qtd_p - 1}")
                    else:
                        st.error(f"❌ Estoque esgotado para o produto: {nome_p}!")
                else:
                    st.warning(f"⚠️ Código de barras '{codigo_bipado}' não encontrado no cadastro de produtos.")
                
                cursor.close()
                conn.close()
            except Exception as e:
                st.error(f"Erro ao processar o código: {e}")

        # --- MÉTODO MANUAL RESERVA (Caso o leitor quebre ou o produto esteja sem etiqueta) ---
        st.markdown("---")
        with st.expander("⌨️ Operação Manual (Sem Leitor / Código Danificado)"):
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
                            st.error("Erro: Quantidade de saída maior do que a disponível!")
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
                                st.success("Manual atualizado com sucesso!")
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
        else:
            st.info("Nenhuma movimentação foi registrada ainda.")