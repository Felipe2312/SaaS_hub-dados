import streamlit as st
import pandas as pd
from supabase import create_client
import io
import mercadopago
import time
import os

# ==========================================
# 🔐 CONFIGURAÇÕES
# ==========================================
st.set_page_config(page_title="DiskLeads", layout="wide", page_icon="🚀")

try:
    SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["supabase"]["url"]
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets["supabase"]["key"]
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN") or st.secrets["mercado_pago"]["access_token"]
    NOME_MARCA = "DiskLeads"
except Exception as e:
    st.error("Erro: Credenciais não configuradas.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
SDK = mercadopago.SDK(MP_ACCESS_TOKEN)

# ==========================================
# 🧠 FUNÇÕES
# ==========================================
def normalizar_categoria(cat_google):
    if not cat_google: return "Outros"
    cat = str(cat_google).lower()
    if any(x in cat for x in ['natural', 'suplemento', 'academia', 'fit']): return "Saúde & Fitness"
    if any(x in cat for x in ['restaurante', 'pizzaria', 'hamburgueria', 'lanchonete', 'padaria']): return "Alimentação"
    if any(x in cat for x in ['médic', 'clinica', 'saúde', 'hospital', 'dentista']): return "Clínicas & Saúde"
    if any(x in cat for x in ['oficina', 'mecânic', 'auto', 'carro']): return "Automotivo"
    if any(x in cat for x in ['advoga', 'jurídic', 'lei', 'contabilidade']): return "Jurídico & Escritórios"
    if any(x in cat for x in ['loja', 'varejo', 'comércio', 'moda', 'vestuário']): return "Varejo & Comércio"
    if any(x in cat for x in ['imobili', 'construtor', 'engenharia', 'reforma']): return "Construção & Imóveis"
    return "Outros"

def fmt_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def calcular_preco(qtd):
    PRECO_BASE = 0.35 
    tabela = [
        {"limite": 200, "preco": 0.35, "nome": "Básico"},
        {"limite": 1000, "preco": 0.25, "nome": "Profissional"},
        {"limite": 5000, "preco": 0.15, "nome": "Business"},
        {"limite": float('inf'), "preco": 0.08, "nome": "Enterprise"}
    ]
    faixa_atual = None
    prox_faixa_info = None

    for i, faixa in enumerate(tabela):
        if qtd <= faixa["limite"]:
            faixa_atual = faixa
            if i + 1 < len(tabela):
                proxima = tabela[i+1]
                prox_faixa_info = {"meta": faixa["limite"] + 1, "preco": proxima["preco"]}
            break
    
    if not faixa_atual: faixa_atual = tabela[-1]

    preco_unitario = faixa_atual["preco"]
    valor_total = qtd * preco_unitario
    
    preco_ancora_ref = 0.50 if qtd < 50 else 0.35
    valor_ancora = qtd * preco_ancora_ref
    
    pct_economia_total = 0
    if valor_ancora > 0:
        pct_economia_total = int(((valor_ancora - valor_total) / valor_ancora) * 100)

    return {
        "unitario": preco_unitario,
        "total": valor_total,
        "total_ancora": valor_ancora,
        "pct_off": pct_economia_total,
        "nivel": faixa_atual["nome"],
        "prox_qtd": prox_faixa_info["meta"] if prox_faixa_info else None,
        "prox_preco": prox_faixa_info["preco"] if prox_faixa_info else None
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
        df['nota'] = pd.to_numeric(df['nota'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        df['bairro'] = df['bairro'].fillna('Não informado')
        df['estado'] = df['estado'].fillna('N/A')
        df['categoria_google'] = df['categoria_google'].fillna('Não identificada')
        df['Segmento'] = df['categoria_google'].apply(normalizar_categoria)
    return df

# ==========================================
# 🖥️ HEADER E INTRO
# ==========================================
df_raw = get_all_data()

st.title(f"🚀 {NOME_MARCA}")
st.markdown("### A plataforma de inteligência de dados locais.")
st.caption("Enriqueça seu CRM com dados públicos, atualizados e validados do Google Maps.")

with st.expander("ℹ️ **O que eu vou receber? (Detalhes dos Dados)**", expanded=False):
    c_info1, c_info2 = st.columns([1.2, 1])
    with c_info1:
        st.markdown("""
        #### 📦 Conteúdo do Arquivo
        Você receberá um arquivo **Excel** gerado na hora contendo:
        * ✅ **Nome da Empresa**
        * ✅ **Telefone** (Misto: Linhas Fixas e Celulares/WhatsApp)
        * ✅ **Endereço Completo** (Rua, Bairro, Cidade, UF, CEP)
        * ✅ **Website** e Link do Google Maps
        * ✅ **Avaliação** e Nicho de Atuação
        """)
        st.warning("⚠️ **Nota:** Como os dados são públicos, é natural que uma pequena porcentagem dos telefones esteja desatualizada ou sejam fixos. Nosso preço baixo já considera essa margem.")
    with c_info2:
        st.markdown("#### 📄 Exemplo Visual")
        df_exemplo = pd.DataFrame({
            "Empresa": ["Padaria Pão Dourado", "Auto Center Silva"],
            "Telefone": ["(11) 99999-1234 📱", "(21) 3344-5566 ☎️"],
            "Tipo": ["Celular/Zap", "Fixo"],
            "Cidade": ["São Paulo", "Rio de Janeiro"],
        })
        st.dataframe(df_exemplo, hide_index=True, use_container_width=True)

st.divider()

# ==========================================
# 🔍 ÁREA DE FILTROS (SEMPRE VISÍVEL)
# ==========================================
with st.container(border=True):
    st.subheader("🛠️ Comece filtrando sua lista")
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: busca_nome = st.text_input("Buscar por Nome (Opcional)", placeholder="Ex: Silva...")
    with c2: nota_range = st.select_slider("Qualidade Mínima", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
    with c3: filtro_site = st.radio("Tem Site?", ["Todos", "Sim", "Não"], horizontal=True)

    t1, t2 = st.tabs(["🎯 Segmentação", "📍 Localização"])
    
    # Lógica de Filtros (Mas não mostra resultados ainda)
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

# Aplicação final dos filtros
df_f = df_bai[df_bai['bairro'].isin(f_bairro)] if f_bairro else df_bai

# ==========================================
# 🚦 LÓGICA DE UX: MOSTRAR RESULTADOS OU DASHBOARD?
# ==========================================

# Verifica se o usuário mexeu em algum filtro
filtros_ativos = any([busca_nome, f_macro, f_google, f_uf, f_cidade, f_bairro])
# OBS: nota_range e filtro_site costumam ser padrão, então só consideramos "ativo" se mexer nos outros
# Mas se quiser ser rigoroso, pode incluir tudo. Vou deixar o básico para "obrigar" uma ação.

if not filtros_ativos:
    # --- ESTADO INICIAL (DASHBOARD GLOBAL) ---
    st.info("👆 **Utilize os filtros acima para começar.** Selecione um Estado, Cidade ou Setor para visualizar os leads disponíveis.")
    
    st.markdown("### 🌎 Nossa Base em Números")
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total de Empresas", f"{len(df_raw):,}".replace(",", "."))
    with m2:
        st.metric("Cidades Cobertas", f"{df_raw['cidade'].nunique()}")
    with m3:
        st.metric("Setores Disponíveis", f"{df_raw['Segmento'].nunique()}")
        
    st.markdown("---")
    st.caption("Aguardando seleção...")

else:
    # --- ESTADO ATIVO (MOSTRA RESULTADOS, PREÇO E COMPRA) ---
    
    # 1. Precificação
    total_leads = len(df_f)
    resumo_preco = calcular_preco(total_leads)
    valor_total = round(resumo_preco['total'], 2)

    st.divider()

    if total_leads == 0:
        st.warning("⚠️ Nenhum lead encontrado com esses filtros. Tente expandir sua busca.")
    else:
        # Bloco de Preço
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                st.caption("Volume Selecionado")
                st.markdown(f"### {total_leads:,}".replace(",", "."))
                cor_badge = "#FFD700" if resumo_preco['nivel'] == "Ouro" else ("#C0C0C0" if resumo_preco['nivel'] == "Prata" else "#CD7F32")
                st.markdown(f"<span style='background-color:{cor_badge}; color:black; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:bold;'>{resumo_preco['nivel'].upper()}</span>", unsafe_allow_html=True)
            with c2:
                st.caption("Preço Unitário")
                st.markdown(f"### {fmt_real(resumo_preco['unitario'])}")
            with c3:
                st.caption("Total a Pagar")
                if resumo_preco['pct_off'] > 0:
                     st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="text-decoration: line-through; color: #ff4b4b; font-size: 14px;">
                            {fmt_real(resumo_preco['total_ancora'])}
                        </span>
                        <span style="background-color: #d4edda; color: #155724; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold;">
                            -{resumo_preco['pct_off']}% OFF
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown(f"<h3 style='color:#2ecc71; margin-top:0px'>{fmt_real(resumo_preco['total'])}</h3>", unsafe_allow_html=True)

            if resumo_preco['prox_qtd']:
                meta = resumo_preco['prox_qtd']
                faltam = meta - total_leads
                prox_preco = resumo_preco['prox_preco']
                economia_extra_pct = int(((resumo_preco['unitario'] - prox_preco) / resumo_preco['unitario']) * 100)
                progresso = min(total_leads / meta, 0.98) 
                st.write("") 
                st.progress(progresso)
                st.info(f"💡 Falta pouco! Adicione apenas **{faltam} leads** para entrar na próxima faixa e pagar **{fmt_real(prox_preco)}/unid** (Redução extra de {economia_extra_pct}% no custo).")

        # 2. Área de Pagamento
        if 'ref_venda' not in st.session_state:
            st.session_state.ref_venda = f"REF_{int(time.time())}"

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
            with st.container(border=True):
                st.subheader("📬 Finalizar Compra")
                ce1, ce2 = st.columns(2)
                with ce1: email_input = st.text_input("Seu E-mail")
                with ce2: email_confirm = st.text_input("Confirme seu E-mail")
                
                pode_prosseguir = (email_input == email_confirm) and ("@" in email_input)

                if st.button("💳 IR PARA PAGAMENTO SEGURO", type="primary", use_container_width=True, disabled=not pode_prosseguir):
                    # Lógica de Checkout (igual anterior)
                    output_file = io.BytesIO()
                    df_f.to_excel(output_file, index=False)
                    nome_arquivo = f"{st.session_state.ref_venda}.xlsx"
                    supabase.storage.from_('leads_pedidos').upload(
                        path=nome_arquivo, 
                        file=output_file.getvalue(), 
                        file_options={"x-upsert": "true", "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
                    )
                    url_publica = supabase.storage.from_('leads_pedidos').get_public_url(nome_arquivo)

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
                        "filtros_json": filtros_cliente
                    }).execute()
                    pref_data = {
                        "items": [{"title": f"Pacote {total_leads} Leads - {NOME_MARCA}", "quantity": 1, "unit_price": float(valor_total), "currency_id": "BRL"}],
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
                        st.error("Erro ao gerar link.")

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

    # 3. Análise Visual (Só aparece se tiver filtros)
    st.divider()
    st.subheader("📊 Raio-X da Base Selecionada")
    g1, g2, g3 = st.columns(3)
    with g1:
        st.write("**Top Cidades**")
        st.bar_chart(df_f['cidade'].value_counts().head(10), color="#2E66F1", horizontal=True)
    with g2:
        st.write("**Top Bairros**")
        st.bar_chart(df_f['bairro'].value_counts().head(10), color="#2ecc71", horizontal=True)
    with g3:
        st.write("**Segmentos**")
        st.bar_chart(df_f['Segmento'].value_counts(), color="#f39c12", horizontal=True)

    st.subheader("📋 Amostra dos Dados (Top 50)")
    colunas_exibicao = {'nome': 'Empresa', 'Segmento': 'Setor', 'categoria_google': 'Nicho', 'bairro': 'Bairro', 'cidade': 'Cidade', 'estado': 'UF', 'nota': 'Nota'}
    cols_exists = [c for c in colunas_exibicao.keys() if c in df_f.columns]
    st.dataframe(df_f[cols_exists].rename(columns=colunas_exibicao).head(50), use_container_width=True, hide_index=True)