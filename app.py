import streamlit as st
import pandas as pd
from supabase import create_client
import io
import mercadopago
import time

# ==========================================
# 🔐 CONFIGURAÇÕES E CREDENCIAIS
# ==========================================
try:
    # Coletando segredos do .streamlit/secrets.toml
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
    MP_ACCESS_TOKEN = st.secrets["mercado_pago"]["access_token"]
    NOME_MARCA = "DiskLeads"
except Exception as e:
    st.error("Erro: Verifique se todos os secrets estão configurados corretamente.")
    st.stop()

# Inicialização dos clientes
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
SDK = mercadopago.SDK(MP_ACCESS_TOKEN)

# ==========================================
# 🧠 FUNÇÕES DE SUPORTE
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
        # Proteção para coluna de data
        if 'data_extracao' in df.columns:
            df['data_extracao'] = pd.to_datetime(df['data_extracao'], errors='coerce').dt.strftime('%d/%m/%Y')
        df['bairro'] = df['bairro'].fillna('Não informado')
        df['estado'] = df['estado'].fillna('N/A')
        df['categoria_google'] = df['categoria_google'].fillna('Não identificada')
        df['Segmento'] = df['categoria_google'].apply(normalizar_categoria)
    return df

# ==========================================
# 🖥️ INTERFACE E FILTROS
# ==========================================
st.set_page_config(page_title=NOME_MARCA, layout="wide", page_icon="📈")
df_raw = get_all_data()

st.title(f"🚀 {NOME_MARCA}")
st.caption("A plataforma mais rápida para extrair contatos B2B qualificados.")

with st.container(border=True):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: busca_nome = st.text_input("Buscar Empresa", placeholder="Digite o nome...")
    with c2: nota_range = st.select_slider("Avaliação Google", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
    with c3: filtro_site = st.radio("Website", ["Todos", "Sim", "Não"], horizontal=True)

    t1, t2 = st.tabs(["🎯 Segmentação", "📍 Localização"])
    
    df_temp = df_raw.copy()
    if busca_nome: df_temp = df_temp[df_temp['nome'].str.contains(busca_nome, case=False, na=False)]
    if filtro_site == "Sim": df_temp = df_temp[df_temp['site'].notnull()]
    elif filtro_site == "Não": df_temp = df_temp[df_temp['site'].isnull()]
    df_temp = df_temp[(df_temp['nota'] >= nota_range[0]) & (df_temp['nota'] <= nota_range[1])]

    with t1:
        col_a, col_b = st.columns(2)
        with col_a:
            f_macro = st.multiselect("Setor Principal", sorted(df_temp['Segmento'].unique()) if not df_temp.empty else [])
        with col_b:
            df_nicho = df_temp[df_temp['Segmento'].isin(f_macro)] if f_macro else df_temp
            f_google = st.multiselect("Nicho Específico", sorted(df_nicho['categoria_google'].unique()) if not df_nicho.empty else [])
            
    with t2:
        df_loc = df_nicho[df_nicho['categoria_google'].isin(f_google)] if f_google else df_nicho
        col_d, col_e, col_f = st.columns(3)
        with col_d:
            f_uf = st.multiselect("Estado (UF)", sorted(df_loc['estado'].unique()) if not df_loc.empty else [])
        with col_e:
            df_cid = df_loc[df_loc['estado'].isin(f_uf)] if f_uf else df_loc
            f_cidade = st.multiselect("Cidade", sorted(df_cid['cidade'].unique()) if not df_cid.empty else [])
        with col_f:
            df_bai = df_cid[df_cid['cidade'].isin(f_cidade)] if f_cidade else df_cid
            f_bairro = st.multiselect("Bairro", sorted(df_bai['bairro'].unique()) if not df_bai.empty else [])

df_f = df_bai[df_bai['bairro'].isin(f_bairro)] if f_bairro else df_bai

# --- PRECIFICAÇÃO ---
total_leads = len(df_f)
preco_un = 0.30 if total_leads <= 500 else (0.20 if total_leads <= 2000 else 0.12)
valor_total = round(total_leads * preco_un, 2)
valor_br = f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.divider()

# ==========================================
# 💰 LÓGICA DE PAGAMENTO (INTEGRADA COM EDGE FUNCTION)
# ==========================================
if 'ref_venda' not in st.session_state:
    st.session_state.ref_venda = f"REF_{int(time.time())}"

# Verifica status atual no banco
check_banco = supabase.table("vendas").select("*").eq("external_reference", st.session_state.ref_venda).execute()
dados_venda = check_banco.data[0] if check_banco.data else None
pago = True if (dados_venda and dados_venda['status'] == 'pago') else False

if pago:
    st.balloons()
    st.success(f"✅ Pagamento Confirmado! Os leads foram enviados para {dados_venda['email_cliente']}")
    
    # Download direto para o usuário que permaneceu na página
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_f.to_excel(writer, index=False, sheet_name='Leads')
    st.download_button("💾 Baixar Arquivo Agora", output.getvalue(), f"leads_{st.session_state.ref_venda}.xlsx", use_container_width=True)
    
    if st.button("🔄 Nova Busca"):
        st.session_state.clear()
        st.rerun()
else:
    m1, m2, m3 = st.columns(3)
    m1.metric("Leads Selecionados", f"{total_leads:,}".replace(",", "."))
    m2.metric("Preço Unitário", f"R$ {preco_un:.2f}".replace(".", ","))
    m3.metric("Total a Pagar", valor_br)

    if total_leads > 0:
        with st.container(border=True):
            st.subheader("📬 Onde deseja receber os dados?")
            ce1, ce2 = st.columns(2)
            with ce1: email_input = st.text_input("Seu E-mail")
            with ce2: email_confirm = st.text_input("Confirme seu E-mail")
            
            pode_prosseguir = (email_input == email_confirm) and ("@" in email_input)

            if st.button("💳 FINALIZAR PEDIDO E RECEBER POR E-MAIL", type="primary", use_container_width=True, disabled=not pode_prosseguir):
                # 1. Gerar Excel e subir para o Storage (Bucket: leads_pedidos)
                output_file = io.BytesIO()
                df_f.to_excel(output_file, index=False)
                nome_arquivo = f"{st.session_state.ref_venda}.xlsx"
                
                # Upload para o Supabase Storage
                # Upload para o Supabase Storage com permissão de sobrescrever (upsert)
                supabase.storage.from_('leads_pedidos').upload(
                    path=nome_arquivo, 
                    file=output_file.getvalue(), 
                    file_options={"x-upsert": "true", "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
                )
                url_publica = supabase.storage.from_('leads_pedidos').get_public_url(nome_arquivo)

                # 2. Salvar venda no Banco (Pendente)
                supabase.table("vendas").upsert({
                    "external_reference": st.session_state.ref_venda,
                    "valor": valor_total,
                    "status": "pendente",
                    "email_cliente": email_input,
                    "url_arquivo": url_publica
                }).execute()

                # 3. Criar Preferência no Mercado Pago
                pref_data = {
                    "items": [{"title": f"Base {total_leads} Leads - {NOME_MARCA}", "quantity": 1, "unit_price": float(valor_total), "currency_id": "BRL"}],
                    "external_reference": st.session_state.ref_venda,
                    "back_urls": {"success": "https://leads-brasil.streamlit.app/"},
                    "auto_return": "approved",
                    "notification_url": "https://wsqebbwjmiwiscbkmawy.supabase.co/functions/v1/smooth-processor" # COLOQUE O NOME REAL DA SUA FUNÇÃO AQUI
                }
                res = SDK.preference().create(pref_data)
                
                if res["status"] in [200, 201]:
                    link_mp = res["response"]["init_point"]
                    st.session_state.link_ativo = link_mp
                    # Abre em nova guia automático
                    st.components.v1.html(f"<script>window.open('{link_mp}', '_blank');</script>", height=0)
                else:
                    st.error("Erro ao gerar link de pagamento.")

            if 'link_ativo' in st.session_state:
                st.info("🕒 Checkout aberto em nova guia. Caso não tenha aberto, clique abaixo:")
                st.markdown(f'<div style="text-align:center;"><a href="{st.session_state.link_ativo}" target="_blank"><button style="padding:12px; background-color:#2e66f1; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">ABRIR PAGAMENTO MANUALMENTE</button></a></div>', unsafe_allow_html=True)
                
                with st.status("Aguardando confirmação do pagamento...") as status:
                    for _ in range(60):
                        time.sleep(3)
                        check = supabase.table("vendas").select("status").eq("external_reference", st.session_state.ref_venda).execute()
                        if check.data and check.data[0]['status'] == 'pago':
                            status.update(label="✅ Pago!", state="complete")
                            st.rerun()
    else:
        st.error("Selecione leads para habilitar o pagamento.")

st.divider()

# --- ANÁLISE VISUAL ---
if not df_f.empty:
    st.subheader("📊 Distribuição da Seleção")
    g1, g2, g3 = st.columns(3)
    with g1:
        st.write("**Top Cidades**")
        st.bar_chart(df_f['cidade'].value_counts().head(10), color="#2E66F1", horizontal=True)
    with g2:
        st.write("**Top Bairros**")
        st.bar_chart(df_f['bairro'].value_counts().head(10), color="#2ecc71", horizontal=True)
    with g3:
        st.write("**Setores**")
        st.bar_chart(df_f['Segmento'].value_counts(), color="#f39c12", horizontal=True)

st.subheader("📋 Amostra dos Dados (Top 50)")
colunas_exibicao = {'nome': 'Empresa', 'Segmento': 'Setor', 'categoria_google': 'Nicho', 'bairro': 'Bairro', 'cidade': 'Cidade', 'estado': 'UF', 'nota': 'Nota'}
# Garante exibição apenas de colunas existentes
cols_exists = [c for c in colunas_exibicao.keys() if c in df_f.columns]
st.dataframe(df_f[cols_exists].rename(columns=colunas_exibicao).head(50), use_container_width=True, hide_index=True)