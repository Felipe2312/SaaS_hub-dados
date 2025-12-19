import streamlit as st
import pandas as pd
from supabase import create_client
import io
import mercadopago

# ==========================================
# 🔐 CONFIGURAÇÕES E CREDENCIAIS (SEGURO)
# ==========================================
try:
    ACCESS_TOKEN = st.secrets["mercado_pago"]["access_token"]
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except Exception as e:
    st.error("Erro: Credenciais não encontradas nos Secrets do Streamlit.")
    st.stop()

SDK = mercadopago.SDK(ACCESS_TOKEN)

# ==========================================
# 🧠 INTELIGÊNCIA DE DADOS
# ==========================================
def normalizar_categoria(cat_google):
    if not cat_google: return "Outros"
    cat = str(cat_google).lower()
    if any(x in cat for x in ['natural', 'suplemento', 'academia', 'fit']): return "Saúde & Fitness"
    if any(x in cat for x in ['restaurante', 'pizzaria', 'hamburgueria', 'lanchonete']): return "Alimentação"
    if any(x in cat for x in ['médic', 'clinica', 'saúde']): return "Clínicas & Saúde"
    if any(x in cat for x in ['oficina', 'mecânic', 'auto']): return "Automotivo"
    if any(x in cat for x in ['advoga', 'jurídic']): return "Jurídico"
    if any(x in cat for x in ['loja', 'varejo', 'comércio']): return "Varejo & Comércio"
    return "Outros"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

@st.cache_data(ttl=600)
def get_all_data():
    all_rows = []
    step = 1000
    start = 0
    while True:
        res = supabase.table("leads").select("*").range(start, start + step - 1).execute()
        rows = res.data
        all_rows.extend(rows)
        if len(rows) < step: break
        start += step
    df = pd.DataFrame(all_rows)
    if not df.empty:
        df['nota'] = pd.to_numeric(df['nota'].str.replace(',', '.'), errors='coerce').fillna(0)
        df['data_extracao'] = pd.to_datetime(df['data_extracao'], errors='coerce').dt.strftime('%d/%m/%Y')
        df['bairro'] = df['bairro'].fillna('Não informado')
        df['estado'] = df['estado'].fillna('N/A')
        df['categoria_google'] = df['categoria_google'].fillna('Não identificada')
        df['Segmento'] = df['categoria_google'].apply(normalizar_categoria)
    return df

# ==========================================
# 🖥️ INTERFACE SAAS
# ==========================================
st.set_page_config(page_title="Leads Intelligence B2B", layout="wide", page_icon="📈")

df_raw = get_all_data()

if df_raw.empty:
    st.info("Sincronizando base de dados...")
    st.stop()

st.title("🚀 Hub de Inteligência B2B")
st.caption("Filtre leads qualificados e adquira a base instantaneamente.")

# --- PAINEL DE FILTROS ---
with st.container(border=True):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: busca_nome = st.text_input("Empresa", placeholder="Nome da empresa...")
    with c2: nota_range = st.select_slider("Avaliação Google", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
    with c3: filtro_site = st.radio("Website", ["Todos", "Sim", "Não"], horizontal=True)

    t1, t2 = st.tabs(["🎯 Segmentação", "📍 Localização"])
    with t1:
        col_a, col_b = st.columns(2)
        with col_a:
            f_macro = st.multiselect("Setor", sorted(df_raw['Segmento'].unique()))
        with col_b:
            df_s = df_raw[df_raw['Segmento'].isin(f_macro)] if f_macro else df_raw
            f_google = st.multiselect("Nicho (Google)", sorted(df_s['categoria_google'].unique()))
    with t2:
        col_d, col_e, col_f = st.columns(3)
        with col_d: f_uf = st.multiselect("UF", sorted(df_s['estado'].unique()))
        with col_e:
            df_l = df_s[df_s['estado'].isin(f_uf)] if f_uf else df_s
            f_cidade = st.multiselect("Cidade", sorted(df_l['cidade'].unique()))
        with col_f:
            df_l = df_l[df_l['cidade'].isin(f_cidade)] if f_cidade else df_l
            f_bairro = st.multiselect("Bairro", sorted(df_l['bairro'].unique()))

# --- PROCESSAMENTO ---
df_f = df_raw.copy()
if f_macro: df_f = df_f[df_f['Segmento'].isin(f_macro)]
if f_google: df_f = df_f[df_f['categoria_google'].isin(f_google)]
if f_uf: df_f = df_f[df_f['estado'].isin(f_uf)]
if f_cidade: df_f = df_f[df_f['cidade'].isin(f_cidade)]
if f_bairro: df_f = df_f[df_f['bairro'].isin(f_bairro)]
if busca_nome: df_f = df_f[df_f['nome'].str.contains(busca_nome, case=False, na=False)]
if filtro_site == "Sim": df_f = df_f[df_f['site'].notnull()]
elif filtro_site == "Não": df_f = df_f[df_f['site'].isnull()]
df_f = df_f[(df_f['nota'] >= nota_range[0]) & (df_f['nota'] <= nota_range[1])]

# --- PRECIFICAÇÃO DINÂMICA ---
total_leads = len(df_f)
preco_un = 0.30 if total_leads <= 500 else (0.20 if total_leads <= 2000 else 0.12)
valor_total = total_leads * preco_un
valor_br = f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==========================================
# 📈 RESULTADOS E MÉTRICAS
# ==========================================
st.write("")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Leads Disponíveis", f"{total_leads:,}".replace(",", "."))
m2.metric("Preço Unitário", f"R$ {preco_un:.2f}")
m3.metric("Média Avaliações", f"{df_f['nota'].mean():.2f} ⭐" if not df_f.empty else "0.00")
m4.metric("Total a Pagar", valor_br)

st.divider()

# ==========================================
# 💰 LÓGICA DE PAGAMENTO E ENTREGA
# ==========================================
params = st.query_params
pago = params.get("status") in ["approved", "success"]

if total_leads > 0:
    if pago:
        st.balloons()
        st.success("✅ Pagamento aprovado! Downloads liberados.")
        c_dl1, c_dl2 = st.columns(2)
        with c_dl1:
            csv_data = df_f.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("💾 Baixar CSV Completo", csv_data, "leads.csv", "text/csv", use_container_width=True)
        with c_dl2:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_f.to_excel(writer, index=False, sheet_name='Leads')
            st.download_button("📊 Baixar Excel Completo", output.getvalue(), "leads.xlsx", use_container_width=True)
    else:
        with st.container(border=True):
            st.warning("🔒 O download está bloqueado até à confirmação do pagamento.")
            if st.button("💳 GERAR LINK DE PAGAMENTO", type="primary", use_container_width=True):
                preference_data = {
                    "items": [{"title": f"Base {total_leads} Leads", "quantity": 1, "unit_price": float(valor_total), "currency_id": "BRL"}],
                    "back_urls": {
                        "success": "https://meu-saas.streamlit.app", # MUDAR APÓS DEPLOY
                        "success": "http://localhost:8501",           # PARA TESTES LOCAIS
                    },
                    "auto_return": "approved",
                }
                try:
                    res = SDK.preference().create(preference_data)
                    link = res["response"]["init_point"]
                    st.markdown(f'### [🚀 Clique aqui para pagar {valor_br}]({link})')
                    st.info("Após o pagamento, você será redirecionado para liberar os arquivos.")
                except Exception as e:
                    st.error(f"Erro ao gerar pagamento: {e}")
else:
    st.error("Selecione leads nos filtros para prosseguir.")

st.divider()
st.subheader("📋 Amostra dos Dados (Top 50)")
st.dataframe(df_f[['nome', 'Segmento', 'categoria_google', 'bairro', 'cidade', 'estado', 'nota']].head(50), use_container_width=True, hide_index=True)

# GRÁFICOS
if not df_f.empty:
    st.subheader("📊 Análise de Distribuição")
    g1, g2 = st.columns(2)
    with g1:
        st.write("**Top Cidades**")
        st.bar_chart(df_f['cidade'].value_counts().head(10), horizontal=True, color="#2E66F1")
    with g2:
        st.write("**Concentração por Bairro**")
        st.bar_chart(df_f['bairro'].value_counts().head(10), horizontal=True, color="#2ecc71")
        