import streamlit as st
import pandas as pd
from supabase import create_client
import io
import mercadopago
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# ==========================================
# 🔐 CONFIGURAÇÕES E CREDENCIAIS
# ==========================================
try:
    ACCESS_TOKEN = st.secrets["mercado_pago"]["access_token"]
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
    GMAIL_USER = st.secrets["gmail"]["email"]
    GMAIL_PASS = st.secrets["gmail"]["password"]
    NOME_MARCA = "DiskLeads"
except Exception as e:
    st.error("Erro: Verifique os Secrets (Mercado Pago, Supabase e Gmail).")
    st.stop()

SDK = mercadopago.SDK(ACCESS_TOKEN)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 📧 FUNÇÃO DE ENVIO DE E-MAIL
# ==========================================
def enviar_email_com_arquivo_storage(destinatario, url_arquivo, ref_venda):
    try:
        # Baixamos o arquivo do storage para anexar no e-mail
        file_data = supabase.storage.from_('leads_pedidos').download(url_arquivo.split('/')[-1])
        
        msg = MIMEMultipart()
        msg['From'] = f"{NOME_MARCA} <{GMAIL_USER}>"
        msg['To'] = destinatario
        msg['Subject'] = f"🚀 Seus Leads do {NOME_MARCA} Chegaram! (Pedido: {ref_venda})"

        corpo_html = f"""
        <html>
        <body style="font-family: sans-serif; color: #333;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 10px;">
                <h2 style="color: #2e66f1;">Pagamento Confirmado! 📈</h2>
                <p>Olá, aqui está o arquivo com os leads que você adquiriu na <strong>{NOME_MARCA}</strong>.</p>
                <p>O arquivo Excel está anexado a este e-mail para sua conveniência.</p>
                <hr style="border:0; border-top:1px solid #eee;">
                <p style="font-size: 11px; color: #999;">Equipe {NOME_MARCA}</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(corpo_html, 'html'))

        part = MIMEBase('application', 'octet-stream')
        part.set_payload(file_data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= leads_{ref_venda}.xlsx")
        msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except:
        return False

# ==========================================
# 🧠 INTELIGÊNCIA DE DADOS
# ==========================================
def normalizar_categoria(cat_google):
    if not cat_google: return "Outros"
    cat = str(cat_google).lower()
    if any(x in cat for x in ['restaurante', 'pizzaria', 'hamburgueria']): return "Alimentação"
    if any(x in cat for x in ['médic', 'clinica', 'saúde']): return "Saúde"
    if any(x in cat for x in ['loja', 'varejo']): return "Varejo"
    return "Outros"

@st.cache_data(ttl=600)
def get_all_data():
    res = supabase.table("leads").select("*").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['nota'] = pd.to_numeric(df['nota'].str.replace(',', '.'), errors='coerce').fillna(0)
        df['data_extracao'] = pd.to_datetime(df['data_extracao']).dt.strftime('%d/%m/%Y')
        df['Segmento'] = df['categoria_google'].apply(normalizar_categoria)
    return df

# ==========================================
# 🖥️ INTERFACE
# ==========================================
st.set_page_config(page_title=NOME_MARCA, layout="wide")
df_raw = get_all_data()

st.title(f"🚀 {NOME_MARCA}")

# --- FILTROS ---
with st.container(border=True):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: busca_nome = st.text_input("Empresa", placeholder="Buscar por nome...")
    with c2: nota_range = st.select_slider("Avaliação Google", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
    with c3: filtro_site = st.radio("Website", ["Todos", "Sim", "Não"], horizontal=True)

    t1, t2 = st.tabs(["🎯 Segmentação", "📍 Localização"])
    
    df_f = df_raw.copy()
    if busca_nome: df_f = df_f[df_f['nome'].str.contains(busca_nome, case=False, na=False)]
    df_f = df_f[(df_f['nota'] >= nota_range[0]) & (df_f['nota'] <= nota_range[1])]
    if filtro_site == "Sim": df_f = df_f[df_f['site'].notnull()]
    elif filtro_site == "Não": df_f = df_f[df_f['site'].isnull()]

    # (Simplificando multiselects para o exemplo)
    with t1:
        f_macro = st.multiselect("Setor Principal", sorted(df_f['Segmento'].unique()))
        if f_macro: df_f = df_f[df_f['Segmento'].isin(f_macro)]
    with t2:
        f_cidade = st.multiselect("Cidade", sorted(df_f['cidade'].unique()))
        if f_cidade: df_f = df_f[df_f['cidade'].isin(f_cidade)]

# --- PRECIFICAÇÃO ---
total_leads = len(df_f)
preco_un = 0.30 if total_leads <= 500 else 0.12
valor_total = round(total_leads * preco_un, 2)
valor_br = f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.divider()

# ==========================================
# 💰 CHECKOUT COM STORAGE
# ==========================================
if 'ref_venda' not in st.session_state:
    st.session_state.ref_venda = f"REF_{int(time.time())}"

# Verifica se a venda já existe e está paga
check_venda = supabase.table("vendas").select("*").eq("external_reference", st.session_state.ref_venda).execute()
dados_venda = check_venda.data[0] if check_venda.data else None
pago = True if (dados_venda and dados_venda['status'] == 'pago') else False

if pago:
    st.balloons()
    st.success(f"✅ Pagamento Confirmado! Enviamos para: {dados_venda['email_cliente']}")
    # Download direto do storage
    file_data = supabase.storage.from_('leads_pedidos').download(dados_venda['url_arquivo'].split('/')[-1])
    st.download_button("💾 Baixar Arquivo Novamente", file_data, f"leads_{st.session_state.ref_venda}.xlsx", use_container_width=True)
else:
    m1, m2, m3 = st.columns(3)
    m1.metric("Leads Selecionados", f"{total_leads:,}".replace(",", "."))
    m2.metric("Preço Unitário", f"R$ {preco_un:.2f}".replace(".", ","))
    m3.metric("Total a Pagar", valor_br)

    if total_leads > 0:
        with st.container(border=True):
            st.subheader("📬 Onde deseja receber os dados?")
            e1, e2 = st.columns(2)
            email_in = e1.text_input("Seu E-mail")
            email_conf = e2.text_input("Confirme seu E-mail")
            
            pode_pagar = (email_in == email_conf) and ("@" in email_in)

            if st.button("💳 FINALIZAR E PAGAR", type="primary", use_container_width=True, disabled=not pode_pagar):
                # 1. Gerar Excel e subir para o Storage
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_f.to_excel(writer, index=False)
                
                file_name = f"{st.session_state.ref_venda}.xlsx"
                supabase.storage.from_('leads_pedidos').upload(file_name, output.getvalue())
                url_publica = supabase.storage.from_('leads_pedidos').get_public_url(file_name)

                # 2. Salvar venda no banco
                supabase.table("vendas").upsert({
                    "external_reference": st.session_state.ref_venda,
                    "valor": valor_total,
                    "status": "pendente",
                    "email_cliente": email_in,
                    "url_arquivo": url_publica
                }).execute()

                # 3. Gerar Mercado Pago
                pref = SDK.preference().create({
                    "items": [{"title": f"Leads B2B {total_leads}", "quantity": 1, "unit_price": float(valor_total), "currency_id": "BRL"}],
                    "external_reference": st.session_state.ref_venda,
                    "back_urls": {"success": "https://leads-brasil.streamlit.app/"},
                    "auto_return": "approved"
                })
                link = pref["response"]["init_point"]
                st.session_state.link_ativo = link
                st.components.v1.html(f"<script>window.open('{link}', '_blank');</script>", height=0)

            if 'link_ativo' in st.session_state:
                st.info("🕒 Checkout aberto. Caso não tenha aparecido:")
                st.markdown(f'<a href="{st.session_state.link_ativo}" target="_blank">ABRIR PAGAMENTO MANUALMENTE</a>', unsafe_allow_html=True)
                
                with st.status("Monitorando pagamento...") as s:
                    for _ in range(60):
                        time.sleep(2)
                        res = supabase.table("vendas").select("status").eq("external_reference", st.session_state.ref_venda).execute()
                        if res.data and res.data[0]['status'] == 'pago':
                            s.update(label="Pago!", state="complete")
                            enviar_email_com_arquivo_storage(email_in, url_publica, st.session_state.ref_venda)
                            st.rerun()

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
colunas_exibicao = {'nome': 'Empresa', 'Segmento': 'Setor', 'categoria_google': 'Nicho', 'bairro': 'Bairro', 'cidade': 'Cidade', 'estado': 'UF', 'nota': 'Nota', 'data_extracao': 'Última Atualização'}
st.dataframe(df_f[list(colunas_exibicao.keys())].rename(columns=colunas_exibicao).head(50), use_container_width=True, hide_index=True)