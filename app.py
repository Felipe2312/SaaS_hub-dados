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
except Exception as e:
    st.error("Erro: Verifique os Secrets (Mercado Pago, Supabase e Gmail).")
    st.stop()

SDK = mercadopago.SDK(ACCESS_TOKEN)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 📧 FUNÇÃO DE ENVIO DE E-MAIL
# ==========================================
def enviar_email_com_anexo(destinatario, df_leads, ref_venda):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = destinatario
        msg['Subject'] = f"✅ Seus Leads estão aqui! (Ref: {ref_venda})"

        corpo = f"""
        Olá! 
        
        Obrigado por adquirir nossa base de leads.
        Segue em anexo o arquivo completo com as empresas filtradas.
        
        Referência do pedido: {ref_venda}
        Total de leads: {len(df_leads)}
        
        Sucesso em suas prospecções!
        """
        msg.attach(MIMEText(corpo, 'plain'))

        # Criar anexo Excel em memória
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_leads.to_excel(writer, index=False, sheet_name='Leads')
        
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(output.getvalue())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= leads_{ref_venda}.xlsx")
        msg.attach(part)

        # Enviar via Servidor Google
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

# ==========================================
# 🧠 INTELIGÊNCIA DE DADOS
# ==========================================
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
        df['data_extracao'] = pd.to_datetime(df['data_extracao']).dt.strftime('%d/%m/%Y')
        df['bairro'] = df['bairro'].fillna('Não informado')
        df['estado'] = df['estado'].fillna('N/A')
        df['categoria_google'] = df['categoria_google'].fillna('Não identificada')
    return df

# ==========================================
# 🖥️ INTERFACE
# ==========================================
st.set_page_config(page_title="Leads Intelligence B2B", layout="wide")
df_raw = get_all_data()

st.title("🚀 Hub de Inteligência B2B")

# --- FILTROS (MANTIDOS CONFORME SUA ÚLTIMA VERSÃO) ---
with st.container(border=True):
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: busca_nome = st.text_input("Empresa", placeholder="Buscar por nome...")
    with c2: nota_range = st.select_slider("Avaliação Google", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
    with c3: filtro_site = st.radio("Website", ["Todos", "Sim", "Não"], horizontal=True)

    t1, t2 = st.tabs(["🎯 Segmentação", "📍 Localização"])
    
    # Lógica de cascata inteligente que você escolheu
    df_temp = df_raw.copy()
    # ... (aplicação de filtros de nome, site, nota) ...

    with t1:
        col_a, col_b = st.columns(2)
        with col_a: f_macro = st.multiselect("Setor Principal", sorted(df_temp['Segmento'].unique()))
        with col_b:
            df_nicho = df_temp[df_temp['Segmento'].isin(f_macro)] if f_macro else df_temp
            f_google = st.multiselect("Nicho Específico (Google)", sorted(df_nicho['categoria_google'].unique()))
    with t2:
        df_loc = df_nicho[df_nicho['categoria_google'].isin(f_google)] if f_google else df_nicho
        col_d, col_e, col_f = st.columns(3)
        with col_d: f_uf = st.multiselect("Estado (UF)", sorted(df_loc['estado'].unique()))
        with col_e:
            df_cid = df_loc[df_loc['estado'].isin(f_uf)] if f_uf else df_loc
            f_cidade = st.multiselect("Cidade", sorted(df_cid['cidade'].unique()))
        with col_f:
            df_bai = df_cid[df_cid['cidade'].isin(f_cidade)] if f_cidade else df_cid
            f_bairro = st.multiselect("Bairro", sorted(df_bai['bairro'].unique()))

df_f = df_bai[df_bai['bairro'].isin(f_bairro)] if f_bairro else df_bai

# --- MÉTRICAS ---
total_leads = len(df_f)
preco_un = 0.30 if total_leads <= 500 else (0.20 if total_leads <= 2000 else 0.12)
valor_total = round(total_leads * preco_un, 2)
valor_br = f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.divider()

# ==========================================
# 💰 LÓGICA DE PAGAMENTO E E-MAIL
# ==========================================
if 'ref_venda' not in st.session_state:
    st.session_state.ref_venda = f"REF_{int(time.time())}"

check_venda = supabase.table("vendas").select("*").eq("external_reference", st.session_state.ref_venda).execute()
pago = True if (check_venda.data and check_venda.data[0]['status'] == 'pago') else False

if pago:
    st.balloons()
    email_cliente = check_venda.data[0].get('email_cliente', 'cliente')
    st.success(f"✅ Pagamento Aprovado! Enviamos a base para: **{email_cliente}**")
    
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button("💾 Baixar CSV", df_f.to_csv(index=False).encode('utf-8-sig'), f"leads_{st.session_state.ref_venda}.csv", "text/csv", use_container_width=True)
    with col_dl2:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_f.to_excel(writer, index=False, sheet_name='Leads')
        st.download_button("📊 Baixar Excel", output.getvalue(), f"leads_{st.session_state.ref_venda}.xlsx", use_container_width=True)
else:
    m1, m2, m3 = st.columns(3)
    m1.metric("Leads Selecionados", f"{total_leads:,}".replace(",", "."))
    m2.metric("Preço Unitário", f"R$ {preco_un:.2f}".replace(".", ","))
    m3.metric("Total a Pagar", valor_br)

    if total_leads > 0:
        with st.container(border=True):
            st.subheader("📬 Onde você quer receber seus leads?")
            ce1, ce2 = st.columns(2)
            with ce1: email_input = st.text_input("Seu E-mail principal", placeholder="email@exemplo.com")
            with ce2: email_confirm = st.text_input("Confirme seu E-mail", placeholder="Repita o email...")
            
            emails_ok = (email_input == email_confirm) and ("@" in email_input)
            
            if email_input and email_confirm and not emails_ok:
                st.error("⚠️ Os e-mails não conferem ou são inválidos.")

            # O botão só habilita se os e-mails forem iguais
            btn_comprar = st.button("💳 FINALIZAR PEDIDO E RECEBER POR E-MAIL", type="primary", use_container_width=True, disabled=not emails_ok)
            
            if btn_comprar:
                # Salva no banco com o email do cliente
                supabase.table("vendas").upsert({
                    "external_reference": st.session_state.ref_venda, 
                    "valor": valor_total, 
                    "status": "pendente",
                    "email_cliente": email_input # Precisa adicionar esta coluna no Supabase!
                }).execute()
                
                pref_data = {
                    "items": [{"title": f"Base {total_leads} Leads B2B", "quantity": 1, "unit_price": float(valor_total), "currency_id": "BRL"}],
                    "external_reference": st.session_state.ref_venda,
                    "back_urls": {"success": "https://leads-brasil.streamlit.app/"},
                    "auto_return": "approved",
                }
                res = SDK.preference().create(pref_data)
                if res["status"] in [200, 201]:
                    link_mp = res["response"]["init_point"]
                    st.session_state.link_ativo = link_mp
                    st.components.v1.html(f"<script>window.open('{link_mp}', '_blank');</script>", height=0)

            if 'link_ativo' in st.session_state:
                st.info("🕒 Aguardando confirmação... Não feche esta tela.")
                st.markdown(f'<div style="text-align:center;"><a href="{st.session_state.link_ativo}" target="_blank"><button style="padding:10px; border-radius:5px; background-color:#2e66f1; color:white; border:none; cursor:pointer;">ABRIR CHECKOUT MANUALMENTE</button></a></div>', unsafe_allow_html=True)
                
                with st.status("Verificando pagamento...", expanded=True) as status_box:
                    for _ in range(60):
                        time.sleep(2)
                        check = supabase.table("vendas").select("status").eq("external_reference", st.session_state.ref_venda).execute()
                        if check.data and check.data[0]['status'] == 'pago':
                            status_box.update(label="✅ Pagamento Detectado!", state="complete")
                            
                            # DISPARO DO E-MAIL
                            status_box.write("📧 Enviando seu arquivo por e-mail...")
                            enviar_email_com_anexo(email_input, df_f, st.session_state.ref_venda)
                            
                            st.rerun()
    else:
        st.error("Selecione leads para prosseguir.")

# --- ANÁLISE VISUAL (GRÁFICOS HORIZONTAIS) ---
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

# --- DATAFRAME COM NOMES PROFISSIONAIS ---
st.subheader("📋 Amostra dos Dados (Top 50)")
colunas_exibicao = {
    'nome': 'Empresa',
    'Segmento': 'Setor',
    'categoria_google': 'Nicho',
    'bairro': 'Bairro',
    'cidade': 'Cidade',
    'estado': 'UF',
    'nota': 'Nota',
    'data_extracao': 'Última Atualização'
}
st.dataframe(
    df_f[list(colunas_exibicao.keys())].rename(columns=colunas_exibicao).head(50), 
    use_container_width=True, 
    hide_index=True
)