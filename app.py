import streamlit as st
import pandas as pd
from supabase import create_client
import io
import os
import urllib.parse
from datetime import datetime

# ==========================================
# 🔐 CONFIGURAÇÕES, ESTILO E LOGIN
# ==========================================
st.set_page_config(page_title="DiskLeads Admin", layout="wide", page_icon="🚀")

st.markdown("""
<style>
    .stDeployButton {display:none;}
    .main .block-container {max-width: 1200px; padding-top: 1rem; margin: auto;}
</style>
""", unsafe_allow_html=True)

def check_password():
    def password_entered():
        if st.session_state["username"] == st.secrets["auth"]["user"] and \
           st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔐 Acesso Restrito")
        st.text_input("Usuário", key="username")
        st.text_input("Senha", type="password", key="password")
        st.button("Entrar", on_click=password_entered)
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔐 Acesso Restrito")
        st.text_input("Usuário", key="username")
        st.text_input("Senha", type="password", key="password")
        st.button("Entrar", on_click=password_entered)
        st.error("😕 Usuário ou senha incorretos.")
        return False
    else:
        return True

if check_password():
    try:
        SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["supabase"]["url"]
        SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets["supabase"]["key"]
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error("Erro nas credenciais do Supabase.")
        st.stop()

    # ==========================================
    # 🛠️ FUNÇÕES DE APOIO
    # ==========================================
    def fmt_real(valor):
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    FRASES_PADRAO = [
        "Oi, tudo bem?", "Opa, tudo certo?", "Olá, tudo bom?", "Oi!", "Opa!",
        "Quem é o responsável por aqui?", "Consigo falar com o dono por aqui?",
        "Esse é o contato da administração?", "Sabe me dizer quem responde pela empresa por aqui?",
        "Por favor, com quem eu falo sobre o imóvel daí?", "O imóvel daí é próprio ou alugado?"
    ]

    def calcular_preco_total(qtd):
        faixas = [{"limite": 500, "preco": 0.18}, {"limite": 2000, "preco": 0.12}, {"limite": 5000, "preco": 0.08}, {"limite": float('inf'), "preco": 0.04}]
        total, ultimo = 0, 0
        for f in faixas:
            if qtd > f["limite"]:
                total += (f["limite"] - ultimo) * f["preco"]
                ultimo = f["limite"]
            else:
                total += (qtd - ultimo) * f["preco"]
                break
        return total

    def formatar_excel(df_input, nome_aba="Leads", eh_amostra=False):
        buffer = io.BytesIO()
        df_exp = df_input.copy()
        
        # Cria os links
        links_puros = []
        for i, (idx, row) in enumerate(df_exp.iterrows()):
            msg = FRASES_PADRAO[0] if eh_amostra else FRASES_PADRAO[i % len(FRASES_PADRAO)]
            num = "".join(filter(str.isdigit, str(row['telefone'])))
            msg_url = urllib.parse.quote(msg)
            links_puros.append(f"https://wa.me/55{num}?text={msg_url}")
        
        df_exp.insert(0, 'LINK WHATSAPP', links_puros)
        
        # LISTA DE COLUNAS DESEJADAS
        cols_desejadas = ['LINK WHATSAPP', 'nome', 'telefone', 'Nicho', 'cidade', 'bairro', 'endereco_completo', 'nota', 'avaliacoes', 'data_fmt', 'site']
        
        # FILTRO: Só usa as colunas que realmente existem no DataFrame (Evita o KeyError: site)
        cols_existentes = [c for c in cols_desejadas if c in df_exp.columns]
        df_final = df_exp[cols_existentes]

        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_final.to_excel(writer, index=False, sheet_name=nome_aba)
            workbook = writer.book
            worksheet = writer.sheets[nome_aba]
            header_fmt = workbook.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#002147', 'border': 1})
            link_style = workbook.add_format({'color': 'blue', 'underline': 1, 'font_size': 9})

            for col_num, value in enumerate(df_final.columns):
                worksheet.write(0, col_num, value, header_fmt)
                worksheet.set_column(col_num, col_num, 25)
                
            for row_num in range(1, len(df_final) + 1):
                url = df_final.iloc[row_num-1]['LINK WHATSAPP']
                worksheet.write_url(row_num, 0, url, link_style, string=url)
        return buffer

    # ==========================================
    # 🔄 DATA LOADER (TRATAMENTO DE NOTAS)
    # ==========================================
    @st.cache_data(ttl=14400, show_spinner=True)
    def carregar_dados():
        all_rows, limit, last_id = [], 1000, 0
        # Puxamos as colunas garantindo que 'site' e as outras estão na query
        cols = "id, nome, telefone, nicho, categoria_google, nota, avaliacoes, endereco_completo, bairro, cidade, estado, data_extracao, tipo_contato, site"
        
        while True:
            try:
                res = supabase.table("leads").select(cols).gt("id", last_id).order("id").limit(limit).execute()
                if not res.data: break
                all_rows.extend(res.data)
                last_id = res.data[-1]['id']
            except:
                break
        
        if not all_rows: return pd.DataFrame()
        
        df = pd.DataFrame(all_rows)
        
        # Ajuste de Nicho
        if 'categoria_google' in df.columns:
            df['nicho'] = df['nicho'].fillna(df['categoria_google'])
        df.rename(columns={'nicho': 'Nicho'}, inplace=True)
        df['Nicho'] = df['Nicho'].fillna("Outros")

        # --- CORREÇÃO DEFINITIVA DAS NOTAS ---
        # Converte para string, limpa, e converte para numérico. 
        # Se for vazio no banco, o coerce transforma em NaN, e o fillna(0) garante o filtro.
        df['nota'] = df['nota'].apply(lambda x: str(x).replace(',', '.') if x is not None and x != "" else "0")
        df['nota'] = pd.to_numeric(df['nota'], errors='coerce').fillna(0.0)
        
        df['avaliacoes'] = pd.to_numeric(df['avaliacoes'], errors='coerce').fillna(0).astype(int)

        # Garantia de preenchimento para filtros não quebrarem
        for col in ['cidade', 'estado', 'bairro', 'site']:
            if col in df.columns:
                df[col] = df[col].fillna("NI")
            else:
                df[col] = "NI" # Cria a coluna caso o banco não retorne

        df['data_extracao'] = pd.to_datetime(df['data_extracao'], errors='coerce')
        df['data_fmt'] = df['data_extracao'].dt.strftime('%d/%m/%Y').fillna("-")
        
        return df

    # ==========================================
    # 🚀 INTERFACE
    # ==========================================
    st.title("🚀 DiskLeads Admin")
    df_raw = carregar_dados()

    if not df_raw.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Leads", f"{len(df_raw):,}".replace(",", "."))
        m2.metric("Cidades", df_raw['cidade'].nunique())
        m3.metric("Nichos", df_raw['Nicho'].nunique())

        t1, t2 = st.tabs(["🎯 Nicho & Data", "📍 Localização"])
        with t1:
            c1, c2 = st.columns([2, 1])
            f_nicho = c1.multiselect("Nicho", sorted(df_raw['Nicho'].unique()))
            f_periodo = c2.selectbox("Período", ["Todo o Período", "Hoje", "Últimos 7 Dias", "Últimos 30 Dias"])
        
        with t2:
            c_d, c_e, c_f = st.columns(3)
            f_uf = c_d.multiselect("Estado (UF)", sorted(df_raw['estado'].unique()))
            opts_cid = df_raw[df_raw['estado'].isin(f_uf)] if f_uf else df_raw
            f_cidade = c_e.multiselect("Cidade", sorted(opts_cid['cidade'].unique()))
            opts_bai = df_raw[df_raw['cidade'].isin(f_cidade)] if f_cidade else df_raw
            f_bairro = c_f.multiselect("Bairro", sorted(opts_bai['bairro'].dropna().unique()))

        with st.container(border=True):
            st.markdown("##### ⚡ Qualidade & Ordenação")
            l1, l2, l3 = st.columns([1, 1.5, 1.5])
            f_cel = l1.checkbox("Apenas Celular", True)
            misturar = l1.checkbox("🔀 Misturar Nichos", False)
            # Slider de nota usando o valor corrigido
            nota_range = l2.slider("Nota Mínima", 0.0, 5.0, (0.0, 5.0), 0.1)
            aval_range = l3.slider("Avaliações", 0, 10000, (0, 10000), 10)

        df_f = df_raw.copy()
        if f_nicho: df_f = df_f[df_f['Nicho'].isin(f_nicho)]
        if f_uf: df_f = df_f[df_f['estado'].isin(f_uf)]
        if f_cidade: df_f = df_f[df_f['cidade'].isin(f_cidade)]
        if f_bairro: df_f = df_f[df_f['bairro'].isin(f_bairro)]
        if f_cel: df_f = df_f[df_f['tipo_contato'] == 'Celular']
        
        # Filtro de nota
        df_f = df_f[(df_f['nota'] >= nota_range[0]) & (df_f['nota'] <= nota_range[1])]
        df_f = df_f[(df_f['avaliacoes'] >= aval_range[0]) & (df_f['avaliacoes'] <= aval_range[1])]

        if misturar: 
            df_f = df_f.sample(frac=1, random_state=42).reset_index(drop=True)
        else: 
            df_f = df_f.sort_values(by=['Nicho', 'nome']).reset_index(drop=True)

        leads_disp = len(df_f)
        if leads_disp > 0:
            st.divider()
            val_range = st.slider("Selecionar Quantidade", 0, leads_disp, (0, min(100, leads_disp)))
            df_venda = df_f.iloc[val_range[0]:val_range[1]]
            
            qtd_f = len(df_venda)
            preco_f = calcular_preco_total(qtd_f)
            
            st.metric("📦 Pacote Selecionado", f"{qtd_f} Leads", fmt_real(preco_f))
            # Mostra a tabela com os dados reais
            st.dataframe(df_venda[['nome', 'telefone', 'Nicho', 'cidade', 'nota', 'avaliacoes']], use_container_width=True)

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🎲 Amostra"):
                    st.download_button("Baixar Amostra", formatar_excel(df_venda.sample(min(3, qtd_f)), "Amostra", True), "Amostra.xlsx", key="amostra_v12")
            with col_b:
                nome_cli = st.text_input("Nome Cliente")
                if st.download_button("🚀 LISTA COMPLETA", formatar_excel(df_venda, "Lista", False), f"Lista_{nome_cli}.xlsx", type="primary", key="lista_v12"):
                    st.success("Download iniciado!")