import streamlit as st
import pandas as pd
from supabase import create_client
import io
import mercadopago
import time
import os

# ==========================================
# 🔐 CONFIGURAÇÕES E CREDENCIAIS
# ==========================================
try:
    SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["supabase"]["url"]
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets["supabase"]["key"]
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN") or st.secrets["mercado_pago"]["access_token"]
    NOME_MARCA = "DiskLeads"
except Exception as e:
    st.error("Erro: Verifique se todos os secrets ou variáveis de ambiente estão configurados.")
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

def fmt_real(valor):
    """Formata float para moeda brasileira R$ 1.234,56"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_preco(qtd):
    """Calcula preço baseado em Tiers com ancoragem no preço base"""
    # Preço Base para comparação (R$ 0,35 - O preço de entrada)
    PRECO_BASE = 0.35 

    tabela = [
        {"limite": 200, "preco": 0.35, "nome": "Básico"},
        {"limite": 1000, "preco": 0.25, "nome": "Profissional"},
        {"limite": 5000, "preco": 0.15, "nome": "Business"},
        {"limite": float('inf'), "preco": 0.08, "nome": "Enterprise"}
    ]

    faixa_atual = None
    proxima_faixa = None

    for i, faixa in enumerate(tabela):
        if qtd <= faixa["limite"]:
            faixa_atual = faixa
            # Pega o PRÓXIMO nível imediato
            if i + 1 < len(tabela):
                proxima_faixa = tabela[i+1]
            break
    
    # Se passou do último limite
    if not faixa_atual:
        faixa_atual = tabela[-1]

    preco_unitario = faixa_atual["preco"]
    valor_total = qtd * preco_unitario
    
    # Ancoragem: Quanto custaria se não tivesse desconto de volume (Preço Base)
    # Se estiver no nível básico, usamos um preço de mercado fictício (0.50) para dar sensação de vantagem
    preco_comparacao = 0.50 if faixa_atual["nome"] == "Básico" else 0.35
    valor_tabela = qtd * preco_comparacao

    return {
        "unitario": preco_unitario,
        "total": valor_total,
        "total_ancora": valor_tabela,
        "nivel": faixa_atual["nome"],
        "prox_qtd": proxima_faixa["limite"] + 1 if proxima_faixa else None,
        "prox_preco": proxima_faixa["preco"] if proxima_faixa else None
    }

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

# ==========================================
# 💲 PRECIFICAÇÃO & CARRINHO (VISUAL REFINADO)
# ==========================================
total_leads = len(df_f)
resumo_preco = calcular_preco(total_leads)
valor_total = round(resumo_preco['total'], 2)

if total_leads > 0:
    st.divider()
    
    with st.expander("ℹ️ Ver Tabela de Descontos por Volume", expanded=False):
        st.markdown("""
        | Quantidade de Leads | Preço por Lead | Categoria |
        | :--- | :--- | :--- |
        | Até 200 | **R$ 0,35** | Básico |
        | 201 a 1.000 | **R$ 0,25** | Profissional |
        | 1.001 a 5.000 | **R$ 0,15** | Business |
        | Acima de 5.000 | **R$ 0,08** | Enterprise |
        """)

    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 1, 1])
        
        with c1:
            st.caption("Volume Selecionado")
            st.markdown(f"### {total_leads:,}".replace(",", "."))
            # Badge de Nível
            cor_badge = "#FFD700" if resumo_preco['nivel'] == "Ouro" else ("#C0C0C0" if resumo_preco['nivel'] == "Prata" else "#CD7F32")
            st.markdown(f"<span style='background-color:{cor_badge}; color:black; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:bold;'>{resumo_preco['nivel'].upper()}</span>", unsafe_allow_html=True)

        with c2:
            st.caption("Preço Unitário")
            st.markdown(f"### {fmt_real(resumo_preco['unitario'])}")
        
        with c3:
            st.caption("Valor Total")
            # Lógica do preço riscado
            if resumo_preco['total'] < resumo_preco['total_ancora']:
                st.markdown(f"""
                <span style="text-decoration: line-through; color: #ff4b4b; font-size: 16px;">
                    {fmt_real(resumo_preco['total_ancora'])}
                </span>
                """, unsafe_allow_html=True)
            
            st.markdown(f"<h3 style='color:#2ecc71; margin-top:-5px'>{fmt_real(resumo_preco['total'])}</h3>", unsafe_allow_html=True)

        # Barra de Progresso
        if resumo_preco['prox_qtd']:
            faltam = resumo_preco['prox_qtd'] - total_leads
            prox_preco = resumo_preco['prox_preco']
            
            # Cálculo de % para o próximo nível
            economia_pct = int(((resumo_preco['unitario'] - prox_preco) / resumo_preco['unitario']) * 100)
            
            # Barra
            limite_anterior = 0 # simplificado
            meta = resumo_preco['prox_qtd']
            progresso = min(total_leads / meta, 0.95)

            st.write("") 
            st.progress(progresso)
            st.info(f"💡 Falta pouco! Adicione mais **{faltam} leads** para entrar na próxima faixa e pagar apenas **{fmt_real(prox_preco)}/unid** (Economia extra de {economia_pct}%).")

else:
    st.divider()
    st.warning("⚠️ Utilize os filtros acima para selecionar os leads que deseja comprar.")

st.divider()

# ==========================================
# 💰 LÓGICA DE PAGAMENTO
# ==========================================
if 'ref_venda' not in st.session_state:
    st.session_state.ref_venda = f"REF_{int(time.time())}"

# Verifica status
check_banco = supabase.table("vendas").select("*").eq("external_reference", st.session_state.ref_venda).execute()
dados_venda = check_banco.data[0] if check_banco.data else None
pago = True if (dados_venda and dados_venda['status'] == 'pago') else False

if pago:
    st.balloons()
    st.success(f"✅ Pagamento Confirmado! Os leads foram enviados para {dados_venda['email_cliente']}")
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_f.to_excel(writer, index=False, sheet_name='Leads')
    st.download_button("💾 Baixar Arquivo Agora", output.getvalue(), f"leads_{st.session_state.ref_venda}.xlsx", use_container_width=True)
    
    if st.button("🔄 Nova Busca"):
        st.session_state.clear()
        st.rerun()
else:
    if total_leads > 0:
        with st.container(border=True):
            st.subheader("📬 Finalizar Compra")
            ce1, ce2 = st.columns(2)
            with ce1: email_input = st.text_input("Seu E-mail")
            with ce2: email_confirm = st.text_input("Confirme seu E-mail")
            
            pode_prosseguir = (email_input == email_confirm) and ("@" in email_input)

            if st.button("💳 IR PARA PAGAMENTO SEGURO", type="primary", use_container_width=True, disabled=not pode_prosseguir):
                output_file = io.BytesIO()
                df_f.to_excel(output_file, index=False)
                nome_arquivo = f"{st.session_state.ref_venda}.xlsx"
                
                supabase.storage.from_('leads_pedidos').upload(
                    path=nome_arquivo, 
                    file=output_file.getvalue(), 
                    file_options={"x-upsert": "true", "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
                )
                url_publica = supabase.storage.from_('leads_pedidos').get_public_url(nome_arquivo)

                # Salva Filtros para o Robô Local
                filtros_cliente = {
                    "setor": f_macro,
                    "nicho": f_google,
                    "cidade": f_cidade,
                    "bairro": f_bairro
                }

                supabase.table("vendas").upsert({
                    "external_reference": st.session_state.ref_venda,
                    "valor": valor_total,
                    "status": "pendente",
                    "email_cliente": email_input,
                    "url_arquivo": url_publica,
                    "enviado": False,
                    # "filtros_json": filtros_cliente 
                }).execute()

                pref_data = {
                    "items": [{"title": f"Base {total_leads} Leads - {NOME_MARCA}", "quantity": 1, "unit_price": float(valor_total), "currency_id": "BRL"}],
                    "external_reference": st.session_state.ref_venda,
                    "back_urls": {"success": "https://leads-brasil.streamlit.app/"},
                    "auto_return": "approved",
                    "notification_url": "https://wsqebbwjmiwiscbkmawy.supabase.co/functions/v1/webhook-pagamento" 
                }
                res = SDK.preference().create(pref_data)
                
                if res["status"] in [200, 201]:
                    link_mp = res["response"]["init_point"]
                    st.session_state.link_ativo = link_mp
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

# --- ANÁLISE VISUAL ---
if not df_f.empty:
    st.subheader("📊 Raio-X da Base Selecionada")
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
cols_exists = [c for c in colunas_exibicao.keys() if c in df_f.columns]
st.dataframe(df_f[cols_exists].rename(columns=colunas_exibicao).head(50), use_container_width=True, hide_index=True)
