import streamlit as st
import pandas as pd
from supabase import create_client
import io
import mercadopago
import time
import os
from datetime import datetime
import math

# ==========================================
# 🔐 CONFIGURAÇÕES E ESTILO
# ==========================================
st.set_page_config(page_title="DiskLeads", layout="wide", page_icon="🚀")

# CSS Ajustado
st.markdown("""
<style>
    .stDeployButton {display:none;}
    
    /* Tooltip do WhatsApp Flutuante */
    .float:hover:after {
        content: "Precisa de ajuda?";
        position: absolute;
        right: 70px;
        top: 15px;
        background: #333;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        white-space: nowrap;
        font-size: 14px;
        box-shadow: 1px 1px 3px #888;
        pointer-events: none;
    }
    
    /* Box de Destaque para Encomenda */
    .box-encomenda {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #2E66F1;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 📞 BOTÃO FLUTUANTE DE SUPORTE ---
def setup_whatsapp_button():
    whatsapp_number = "5511963048466"
    whatsapp_message = "Olá, preciso de ajuda com o DiskLeads."
    
    st.markdown("""
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/font-awesome/4.5.0/css/font-awesome.min.css">
    <style>
    .float{
        position:fixed;
        width:60px;
        height:60px;
        bottom:40px;
        right:40px;
        background-color:#25d366;
        color:#FFF;
        border-radius:50px;
        text-align:center;
        font-size:30px;
        box-shadow: 2px 2px 3px #999;
        z-index:100;
        display:flex;
        align-items:center;
        justify-content:center;
        text-decoration:none;
        transition: all 0.3s ease;
    }
    .float:hover{
        background-color:#128C7E;
        color:#FFF;
        transform: scale(1.1);
    }
    .my-float{
        margin-top:0px;
    }
    </style>
    <a href="https://wa.me/%s?text=%s" class="float" target="_blank">
    <i class="fa fa-whatsapp my-float"></i>
    </a>
    """ % (whatsapp_number, whatsapp_message.replace(" ", "%20")), unsafe_allow_html=True)

setup_whatsapp_button()

# Conexão com Secrets
try:
    SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["supabase"]["url"]
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets["supabase"]["key"]
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN") or st.secrets["mercado_pago"]["access_token"]
    NOME_MARCA = "DiskLeads"
except Exception as e:
    st.error("Erro: Verifique se todos os secrets estão configurados corretamente (arquivo .env ou secrets.toml).")
    st.stop()

# Clientes
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
SDK = mercadopago.SDK(MP_ACCESS_TOKEN)

# --- FUNÇÕES AUXILIARES ---

def fmt_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_link_wa(row):
    if str(row['tipo_contato']) == "Celular":
        nums = "".join(filter(str.isdigit, str(row['telefone'])))
        return f"https://wa.me/{nums}"
    return ""

def calcular_preco_final(qtd):
    # Nova Tabela: 0.18 -> 0.12 -> 0.08 -> 0.04
    faixas = [
        {"limite": 500, "preco": 0.18},    
        {"limite": 2000, "preco": 0.12},
        {"limite": 5000, "preco": 0.08}, 
        {"limite": float('inf'), "preco": 0.04} 
    ]
    total = 0
    ultimo_limite = 0
    prox_meta = None
    prox_preco_meta = None
    
    for i, f in enumerate(faixas):
        if qtd > f["limite"]:
            quantidade_nesta_faixa = f["limite"] - ultimo_limite
            total += quantidade_nesta_faixa * f["preco"]
            ultimo_limite = f["limite"]
        else:
            quantidade_restante = qtd - ultimo_limite
            if quantidade_restante > 0:
                total += quantidade_restante * f["preco"]
            if i + 1 < len(faixas):
                prox_meta = f["limite"]
                prox_preco_meta = faixas[i+1]["preco"]
            break
            
    preco_medio = total / qtd if qtd > 0 else 0.18
    # Valor âncora baseado no preço inicial para mostrar o ganho de escala
    valor_ancora = qtd * 0.18 
    pct_off = int(((valor_ancora - total) / valor_ancora) * 100) if valor_ancora > 0 else 0
    
    return {
        "unitario_medio": preco_medio,
        "total": total,
        "total_ancora": valor_ancora,
        "pct_off": pct_off,
        "prox_qtd": prox_meta,
        "prox_preco_marginal": prox_preco_meta
    }

# --- TEXTO DO BANNER DE ENCOMENDA ---
def render_encomenda_banner():
    with st.container(border=True):
        c_txt, c_btn = st.columns([3, 1])
        with c_txt:
            st.markdown("##### 🕵️ Não encontrou o nicho ou cidade exata?")
            st.caption("Encomende uma **Varredura Sob Medida**. Como vamos extrair agora para você, sai **25% mais barato** que a tabela do site pela espera.")
        with c_btn:
            msg_banner = "Olá, não encontrei o filtro exato no site e gostaria de encomendar uma varredura personalizada com o desconto de 25%."
            st.link_button("Encomendar c/ Desconto", f"https://wa.me/5511963048466?text={msg_banner.replace(' ', '%20')}", use_container_width=True)

# ==============================================================
# 🚀 DATA LOADER
# ==============================================================
CACHE_FILE = "data/leads.parquet"

@st.cache_data(ttl=60, show_spinner=False)
def get_local_data():
    if not os.path.exists(CACHE_FILE):
        return pd.DataFrame()
    try:
        df = pd.read_parquet(CACHE_FILE)
        if 'segmento' in df.columns:
            df.rename(columns={'segmento': 'Segmento'}, inplace=True)
        if 'data_extracao' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['data_extracao']):
                df['data_extracao'] = pd.to_datetime(df['data_extracao'], errors='coerce')
            df['data_fmt'] = df['data_extracao'].dt.strftime('%d/%m/%Y').fillna(datetime.today().strftime('%d/%m/%Y'))
        else:
            df['data_fmt'] = datetime.today().strftime('%d/%m/%Y')
        return df
    except Exception as e:
        return pd.DataFrame()

# ==========================================
# 🚀 LÓGICA DE FLUXO
# ==========================================

if 'ref_venda' not in st.session_state:
    st.session_state.ref_venda = f"REF_{int(time.time())}"

check_banco = supabase.table("vendas").select("*").eq("external_reference", st.session_state.ref_venda).execute()
is_pago = check_banco.data and check_banco.data[0]['status'] == 'pago'

st.title(f"🚀 {NOME_MARCA}")

# -----------------------------------------------------------------
# CENÁRIO A: JÁ PAGO
# -----------------------------------------------------------------
if is_pago:
    st.balloons()
    st.success("✅ **PAGAMENTO CONFIRMADO!**")
    st.info("Baixe seu arquivo abaixo. O link também foi enviado para o seu e-mail.")
    
    nome_arquivo = f"{st.session_state.ref_venda}.xlsx"
    try:
        arquivo_bin = supabase.storage.from_('leads_pedidos').download(nome_arquivo)
        c_down1, c_down2 = st.columns([2, 1])
        with c_down1:
            st.download_button(
                label="📥 BAIXAR MINHA PLANILHA",
                data=arquivo_bin,
                file_name=f"leads_{st.session_state.ref_venda}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
        with c_down2:
            if st.button("🔄 Nova Busca", use_container_width=True):
                st.session_state.clear()
                st.rerun()
    except Exception as e:
        st.error("Erro ao recuperar arquivo. Contate o suporte.")

# -----------------------------------------------------------------
# CENÁRIO B: NÃO PAGO
# -----------------------------------------------------------------
else:
    st.markdown("### A plataforma de inteligência de dados locais.")
    st.caption("Enriqueça seu CRM com dados públicos, atualizados e validados do Google Maps.")
    st.info("💡 **Como usar:** 1. Filtre pelo seu Nicho e Cidade > 2. Baixe uma amostra grátis > 3. Garanta a lista completa.")

    with st.expander("ℹ️ **Entenda o nosso Modelo de Economia**", expanded=False):
        c_info1, c_info2 = st.columns([1.2, 1])
        with c_info1:
            st.markdown("#### 📦 O que você recebe?")
            st.markdown("""
            * 🟢 **WhatsApp Direto:** Link pronto para abrir a conversa.
            * 📡 **Dados Vivos:** Extraídos agora do Google Maps.
            * 🚫 **Sem Dados de CNPJ:** Chega de falar com o contador.
            * 📍 **Foco Local:** Filtre por bairro e cidade com precisão.
            * ⭐ **Qualidade:** Saiba quem são os melhores da região.
            """)
        with c_info2:
            st.markdown("#### 📉 Descontos Progressivos")
            st.markdown("""
            | Faixa de Volume | Preço por Lead |
            | :--- | :--- |
            | Até 500 leads | **R$ 0,18** |
            | 501 a 2.000 leads | **R$ 0,12** |
            | 2.001 a 5.000 leads | **R$ 0,08** |
            | Acima de 5.000 leads | **R$ 0,04** |
            """)
            st.caption("O desconto é aplicado progressivamente no checkout.")

    st.divider()

    df_raw = get_local_data()

    if df_raw.empty:
        st.warning("🔄 **Sincronizando Base de Dados...**")
        st.write("Estamos otimizando os arquivos no servidor. Aguarde 1 minuto e recarregue.")
        if st.button("🔄 Recarregar Página"): st.rerun()
    
    else:
        # --- FILTROS INTELIGENTES (CASCATA) ---
        # A lógica aqui é filtrar as opções DISPONÍVEIS baseado no que já foi filtrado antes.
        
        with st.container(border=True):
            st.subheader("🛠️ Configure sua Lista")
            
            # --- 1. FILTROS TÉCNICOS (TOPO DO FUNIL) ---
            c2, c3, c4, c5 = st.columns([1.5, 1.5, 1, 1])
            
            with c2: 
                nota_range = st.select_slider("⭐ Nota Mínima", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0), help="Filtre pela qualidade.")
            with c3: 
                avaliacoes_range = st.slider("🗣️ Qtd. Avaliações", 0, 5000, (0, 5000), step=10, help="Filtre pela popularidade.")
            with c4: 
                filtro_site = st.radio("🌐 Tem Site?", ["Todos", "Sim", "Não"], horizontal=True)
            with c5: 
                filtro_tel = st.radio("📞 Telefone", ["Todos", "Celular", "Fixo"], horizontal=True, index=0)

            st.divider()

            # --- LÓGICA DE CASCATA (PREPARAÇÃO DOS DADOS) ---
            # Aqui aplicamos os filtros técnicos ANTES de gerar as opções de lista
            # Isso garante que se filtrar "Com Site", só aparecem cidades que têm empresas com site.
            
            df_step1 = df_raw.copy()

            # Aplica Site
            if filtro_site == "Sim": df_step1 = df_step1[df_step1['site'].notnull()]
            elif filtro_site == "Não": df_step1 = df_step1[df_step1['site'].isnull()]

            # Aplica Telefone
            if filtro_tel == "Celular": df_step1 = df_step1[df_step1['tipo_contato'] == 'Celular']
            elif filtro_tel == "Fixo": df_step1 = df_step1[df_step1['tipo_contato'] == 'Fixo']

            # Aplica Notas e Avaliações
            df_step1['nota'] = pd.to_numeric(df_step1['nota'], errors='coerce').fillna(0)
            df_step1 = df_step1[(df_step1['nota'] >= nota_range[0]) & (df_step1['nota'] <= nota_range[1])]
            
            df_step1['avaliacoes'] = pd.to_numeric(df_step1['avaliacoes'], errors='coerce').fillna(0)
            min_aval, max_aval = avaliacoes_range
            if max_aval < 5000:
                df_step1 = df_step1[(df_step1['avaliacoes'] >= min_aval) & (df_step1['avaliacoes'] <= max_aval)]
            else:
                df_step1 = df_step1[df_step1['avaliacoes'] >= min_aval]

            # --- 2. ABAS DE SELEÇÃO (POPULADAS COM DADOS FILTRADOS) ---
            t1, t2 = st.tabs(["🎯 Segmentação (Obrigatório)", "📍 Localização (Opcional)"])

            f_macro, f_google, f_uf, f_cidade, f_bairro = [], [], [], [], []

            with t1:
                st.caption("Siga a ordem: Primeiro escolha o setor geral, depois refine a atividade específica.")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("##### 1️⃣ Escolha o Grande Setor")
                    # Popula usando df_step1 (já filtrado tecnicamente)
                    opts_macro = sorted(df_step1['Segmento'].dropna().unique().astype(str).tolist())
                    f_macro = st.multiselect(
                        "Categoria Geral", 
                        opts_macro, 
                        placeholder="Ex: Saúde, Alimentação...",
                        help="Agrupamento amplo das empresas."
                    )
                
                with col_b:
                    # Filtra nichos baseado no Macro selecionado
                    if f_macro: 
                        df_nicho_opts = df_step1[df_step1['Segmento'].isin(f_macro)]
                    else: 
                        df_nicho_opts = df_step1
                    
                    st.markdown("##### 2️⃣ Escolha a Especialidade")
                    opts_nicho = sorted(df_nicho_opts['categoria_google'].dropna().unique().astype(str).tolist())
                    f_google = st.multiselect(
                        "Atividade Específica (Google)", 
                        opts_nicho, 
                        placeholder="Ex: Cardiologista, Pizzaria...",
                        help="A categoria exata cadastrada no Google Maps."
                    )

            # --- PREPARA STEP 2 (DADOS PARA LOCALIZAÇÃO) ---
            # Agora filtramos pelos segmentos escolhidos para limpar as cidades
            df_step2 = df_step1.copy()
            if f_macro: df_step2 = df_step2[df_step2['Segmento'].isin(f_macro)]
            if f_google: df_step2 = df_step2[df_step2['categoria_google'].isin(f_google)]

            with t2:
                col_d, col_e, col_f = st.columns(3)
                
                with col_d:
                    # Popula UF usando df_step2 (filtrado por técnico + segmento)
                    opts_uf = sorted(df_step2['estado'].dropna().unique().astype(str).tolist())
                    f_uf = st.multiselect("Estado (UF)", opts_uf, placeholder="Selecione...")
                
                with col_e:
                    if f_uf: 
                        df_cid_opts = df_step2[df_step2['estado'].isin(f_uf)]
                    else: 
                        df_cid_opts = df_step2
                    
                    opts_cidade = sorted(df_cid_opts['cidade'].dropna().unique().astype(str).tolist())
                    f_cidade = st.multiselect("Cidade", opts_cidade, placeholder="Ex: Campinas...")
                
                with col_f:
                    if f_cidade: 
                        df_bai_opts = df_cid_opts[df_cid_opts['cidade'].isin(f_cidade)]
                    else: 
                        df_bai_opts = df_cid_opts
                    
                    opts_bairro = sorted(df_bai_opts['bairro'].dropna().unique().astype(str).tolist())
                    f_bairro = st.multiselect("Bairro", opts_bairro, placeholder="Selecione...")

        # --- APLICAÇÃO DOS FILTROS FINAIS (CONSOLIDAÇÃO) ---
        # Aqui pegamos o df_step2 (que já tem quase tudo) e aplicamos só a localização final
        df_f = df_step2.copy()

        if f_uf: df_f = df_f[df_f['estado'].isin(f_uf)]
        if f_cidade: df_f = df_f[df_f['cidade'].isin(f_cidade)]
        if f_bairro: df_f = df_f[df_f['bairro'].isin(f_bairro)]

        # Lógica para mostrar o botão de ação
        filtro_aval_ativo = (avaliacoes_range[0] > 0) or (avaliacoes_range[1] < 5000)
        filtros_ativos = any([f_macro, f_google, f_uf, f_cidade, f_bairro, filtro_aval_ativo])

        # --- APLICAÇÃO DOS FILTROS FINAIS ---
        df_f = df_raw.copy()

        # [REMOVIDO AQUI O FILTRO DE NOME]
        
        if filtro_tel == "Celular":
            df_f = df_f[df_f['tipo_contato'] == 'Celular']
        elif filtro_tel == "Fixo":
            df_f = df_f[df_f['tipo_contato'] == 'Fixo']

        if filtro_site == "Sim": df_f = df_f[df_f['site'].notnull()]
        elif filtro_site == "Não": df_f = df_f[df_f['site'].isnull()]

        df_f['nota'] = pd.to_numeric(df_f['nota'], errors='coerce').fillna(0)
        df_f = df_f[(df_f['nota'] >= nota_range[0]) & (df_f['nota'] <= nota_range[1])]

        df_f['avaliacoes'] = pd.to_numeric(df_f['avaliacoes'], errors='coerce').fillna(0)
        min_aval, max_aval = avaliacoes_range
        if max_aval == 5000:
            df_f = df_f[df_f['avaliacoes'] >= min_aval]
        else:
            df_f = df_f[(df_f['avaliacoes'] >= min_aval) & (df_f['avaliacoes'] <= max_aval)]

        if f_macro: df_f = df_f[df_f['Segmento'].isin(f_macro)]
        if f_google: df_f = df_f[df_f['categoria_google'].isin(f_google)]
        if f_uf: df_f = df_f[df_f['estado'].isin(f_uf)]
        if f_cidade: df_f = df_f[df_f['cidade'].isin(f_cidade)]
        if f_bairro: df_f = df_f[df_f['bairro'].isin(f_bairro)]

        filtro_aval_ativo = (avaliacoes_range[0] > 0) or (avaliacoes_range[1] < 5000)
        # [REMOVIDO AQUI O BUSCA_NOME DA LISTA DE ATIVOS]
        filtros_ativos = any([f_macro, f_google, f_uf, f_cidade, f_bairro, filtro_aval_ativo])

        if not filtros_ativos:
            st.info("👆 Selecione um filtro acima para começar a minerar.")
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Empresas Disponíveis", f"{len(df_raw):,}".replace(",", "."))
            with m2: st.metric("Cidades", f"{df_raw['cidade'].nunique()}")
            with m3: st.metric("Setores", f"{df_raw['Segmento'].nunique()}")
            st.markdown("---")
            
            # MOSTRA O BANNER DE ENCOMENDA MESMO SEM FILTRO (PEDIDO DO CLIENTE)
            render_encomenda_banner()

        else:
            total_leads = len(df_f)
            resumo_preco = calcular_preco_final(total_leads)
            valor_total = round(resumo_preco['total'], 2)

            st.divider()

            if total_leads == 0:
                st.info("🔍 Nenhum resultado encontrado para essa combinação específica.")
                render_encomenda_banner()

            else:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 1, 1.3])
                    with c1:
                        st.markdown(f"**Volume** \n## {total_leads:,}".replace(",", "."), unsafe_allow_html=True)
                        st.caption("Leads selecionados")
                    
                    with c2:
                        st.markdown(f"**Média/Lead** \n## {fmt_real(resumo_preco['unitario_medio'])}", unsafe_allow_html=True)
                        st.caption("Preço dinâmico")
                    
                    with c3:
                        valor_total = round(resumo_preco['total'], 2)
                        if resumo_preco['pct_off'] > 0:
                            st.markdown(f"""
                                <p style='margin-bottom: -5px; color: #888; font-size: 14px;'><s>{fmt_real(resumo_preco['total_ancora'])}</s></p>
                                <h2 style='color: #2ecc71; margin-top: 0px;'>{fmt_real(valor_total)}</h2>
                            """, unsafe_allow_html=True)
                            st.markdown(f"<span style='background-color: #d4edda; color: #155724; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;'>📉 ECONOMIA DE {resumo_preco['pct_off']}%</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**Total** \n## {fmt_real(valor_total)}", unsafe_allow_html=True)

                    # Barra de progresso minimalista para a próxima faixa
                    if resumo_preco['prox_qtd']:
                        st.write("")
                        faltam = resumo_preco['prox_qtd'] - total_leads
                        st.caption(f"Adicione mais **{faltam}** leads para baixar o preço para **{fmt_real(resumo_preco['prox_preco_marginal'])}**")
                        st.progress(min(total_leads / resumo_preco['prox_qtd'], 1.0))
                
                # Banner de encomenda abaixo dos resultados também (reforço)
                render_encomenda_banner()
                
                st.write("") 

                with st.container(border=True):
                    st.subheader("📬 Finalizar Compra")
                    
                    # --- INPUTS (Email e Cupom lado a lado) ---
                    c1, c2 = st.columns([2, 1])
                    
                    with c1:
                        ce_a, ce_b = st.columns(2)
                        with ce_a: email_input = st.text_input("Seu E-mail", placeholder="ex: joao@gmail.com")
                        with ce_b: email_confirm = st.text_input("Confirme E-mail", placeholder="Repita o e-mail")
                        
                        # --- [NOVO] AVISO DISCRETO DE E-MAIL ---
                        if email_input and email_confirm and (email_input != email_confirm):
                            st.markdown(f"<span style='color:#e74c3c; font-size:12px; margin-top:-15px; display:block;'>❌ Os e-mails não coincidem. Verifique a digitação.</span>", unsafe_allow_html=True)
                    
                    with c2:
                        cupom_input = st.text_input("Cupom de Desconto", placeholder="Código").upper().strip()

                    # --- LÓGICA DO DESCONTO ---
                    fator_desconto = 0.0
                    msg_cupom = None

                    if cupom_input == "FOUNDER50":
                        fator_desconto = 0.50
                        msg_cupom = "✅ Cupom FOUNDER50 aplicado!"
                    elif cupom_input == "INSTA15":
                        fator_desconto = 0.15
                        msg_cupom = "✅ Cupom INSTA15 aplicado!"
                    elif cupom_input == "FACE15":
                        fator_desconto = 0.15
                        msg_cupom = "✅ Cupom FACE15 aplicado!"
                    elif cupom_input:
                        msg_cupom = "❌ Cupom inválido."

                    # Cálculo final
                    valor_final_pagar = valor_total * (1 - fator_desconto)
                    economia = valor_total - valor_final_pagar

                    st.divider()

                    # --- EXIBIÇÃO DO PREÇO (Nativo e Minimalista) ---
                    cp1, cp2 = st.columns([2, 1])
                    
                    with cp1:
                        # Feedback do Cupom
                        if fator_desconto > 0:
                            st.success(msg_cupom)
                        elif cupom_input:
                            st.caption(f"❌ O cupom **{cupom_input}** não é válido.") # Mudei de st.error para st.caption para ser mais discreto aqui também
                        else:
                            st.caption("Confira seus dados antes de pagar.")

                    with cp2:
                        # O componente st.metric é o mais bonito e limpo para preços
                        if fator_desconto > 0:
                            st.metric(
                                label="Valor Final", 
                                value=fmt_real(valor_final_pagar), 
                                delta=f"Economia de {fmt_real(economia)}",
                                delta_color="normal" # Fica verde indicando coisa boa
                            )
                        else:
                            st.metric(
                                label="Valor Total", 
                                value=fmt_real(valor_total)
                            )

                    # --- BOTÃO DE PAGAMENTO ---
                    st.write("") # Espaçinho
                    
                    # (Removi o st.warning antigo daqui)
                    
                    pode_prosseguir = (email_input == email_confirm) and ("@" in email_input)
                    
                    if st.button(f"💳 PAGAR {fmt_real(valor_final_pagar)}", type="primary", use_container_width=True, disabled=not pode_prosseguir):
                        
                        # --- PREPARAÇÃO DOS DADOS ---
                        lista_filtros = []
                        if f_macro: lista_filtros.append(f"Setor: {', '.join(f_macro)}")
                        if f_google: lista_filtros.append(f"Nicho: {', '.join(f_google)}")
                        if f_uf: lista_filtros.append(f"UF: {', '.join(f_uf)}")
                        if f_cidade: lista_filtros.append(f"Cidade: {', '.join(f_cidade)}")
                        if f_bairro: lista_filtros.append(f"Bairro: {', '.join(f_bairro)}")
                        if filtro_tel != "Todos (Móvel/Fixo)": lista_filtros.append(f"Tel: {filtro_tel}")
                        if nota_range != (0.0, 5.0): lista_filtros.append(f"Nota: {nota_range[0]}-{nota_range[1]}")
                        
                        resumo_filtros_str = " | ".join(lista_filtros) if lista_filtros else "Todos os dados"
                        
                        # Definindo qual cupom será salvo (apenas se for válido)
                        cupom_salvar = cupom_input if fator_desconto > 0 else None

                        # Geração Excel (Mantido Igual)
                        df_final = pd.DataFrame()
                        df_final['Empresa'] = df_f['nome']
                        df_final['Tipo de Telefone'] = df_f['tipo_contato']
                        df_final['Telefone'] = df_f['telefone']
                        df_final['Link WhatsApp'] = df_f.apply(gerar_link_wa, axis=1)
                        df_final['Atualizado em'] = df_f['data_fmt']
                        df_final['Setor Principal'] = df_f['Segmento']
                        df_final['Nicho Específico'] = df_f['categoria_google']
                        df_final['Nota Google'] = df_f['nota']
                        df_final['Qtd Avaliações'] = df_f['avaliacoes']
                        df_final['Endereço Completo'] = df_f['endereco_completo']
                        df_final['Bairro'] = df_f['bairro']
                        df_final['Cidade'] = df_f['cidade']
                        df_final['UF'] = df_f['estado']
                        df_final['Site'] = df_f['site']

                        output_file = io.BytesIO()
                        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
                            df_final.to_excel(writer, index=False, sheet_name='Leads')
                            worksheet = writer.sheets['Leads']
                            worksheet.set_column('A:A', 30)
                            worksheet.set_column('D:D', 25)

                        nome_arquivo = f"{st.session_state.ref_venda}.xlsx"
                        supabase.storage.from_('leads_pedidos').upload(
                            path=nome_arquivo, 
                            file=output_file.getvalue(), 
                            file_options={"x-upsert": "true", "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
                        )
                        url_publica = supabase.storage.from_('leads_pedidos').get_public_url(nome_arquivo)

                        # --- [ATUALIZADO] SALVA VENDA COM A COLUNA CUPOM ---
                        dados_venda = {
                            "external_reference": st.session_state.ref_venda,
                            "valor": valor_final_pagar,
                            "status": "pendente",
                            "email_cliente": email_input,
                            "url_arquivo": url_publica,
                            "detalhes_filtro": resumo_filtros_str,
                            "cupom": cupom_salvar
                        }
                        
                        supabase.table("vendas").upsert(dados_venda).execute()

                        # Checkout Mercado Pago
                        pref_data = {
                            "items": [{"title": f"Base {total_leads} Leads - {NOME_MARCA}", "quantity": 1, "unit_price": float(valor_final_pagar), "currency_id": "BRL"}],
                            "external_reference": st.session_state.ref_venda,
                            "back_urls": {"success": "https://leads-brasil.streamlit.app/"},
                            "auto_return": "approved",
                            "notification_url": "https://wsqebbwjmiwiscbkmawy.supabase.co/functions/v1/smooth-processor"
                        }
                        res = SDK.preference().create(pref_data)
                        
                        if res["status"] in [200, 201]:
                            link_mp = res["response"]["init_point"]
                            st.session_state.link_ativo = link_mp
                            st.components.v1.html(f"<script>window.open('{link_mp}', '_blank');</script>", height=0)
                        else:
                            st.error("Erro na comunicação com Mercado Pago.")

                    if 'link_ativo' in st.session_state:
                        st.info("🕒 Checkout aberto em nova aba.")
                        st.markdown(f'<div style="text-align:center;"><a href="{st.session_state.link_ativo}" target="_blank"><button style="padding:12px; background-color:#2e66f1; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">ABRIR PAGAMENTO AGORA</button></a></div>', unsafe_allow_html=True)
                        
                        with st.status("Aguardando pagamento...") as status:
                            for _ in range(60):
                                time.sleep(3)
                                check = supabase.table("vendas").select("status").eq("external_reference", st.session_state.ref_venda).execute()
                                
                                if check.data and check.data[0]['status'] == 'pago':
                                    status.update(label="✅ Pagamento Confirmado!", state="complete")
                                    st.rerun() # Recarrega a página para mostrar o download
                            
                            # Se o loop acabar e não pagou, avisa
                            status.update(label="⏳ Tempo de verificação automática esgotado.", state="error")
                            st.write("Não identificamos o pagamento nos últimos 3 minutos.")
                        
                        # --- [NOVO] BOTÃO DE CHECAGEM MANUAL ---
                        st.write("")
                        st.markdown("##### Já realizou o pix e não liberou?")
                        if st.button("🔄 CLIQUE AQUI PARA ATUALIZAR STATUS"):
                             # Ao clicar, o Streamlit roda o script todo de novo.
                             # Como o check de 'is_pago' está lá no topo do código,
                             # ele vai bater no banco, ver que tá pago e mostrar a tela de sucesso.
                             st.rerun()
            st.divider()
            st.subheader("📋 Amostra dos Dados (Top 5)")
            
            if total_leads > 0:
                st.markdown(" Quer validar antes? Baixe os **5 primeiros leads** completos agora.")
                
                raw_amostra = df_f.head(5).copy()
                for col in raw_amostra.select_dtypes(['category']).columns:
                    raw_amostra[col] = raw_amostra[col].astype(str)

                df_amostra_final = pd.DataFrame()
                df_amostra_final['Empresa'] = raw_amostra['nome']
                df_amostra_final['Tipo de Telefone'] = raw_amostra['tipo_contato']
                df_amostra_final['Telefone'] = raw_amostra['telefone']
                df_amostra_final['Link WhatsApp'] = raw_amostra.apply(gerar_link_wa, axis=1)
                df_amostra_final['Atualizado em'] = raw_amostra['data_fmt']
                df_amostra_final['Setor Principal'] = raw_amostra['Segmento']
                df_amostra_final['Nicho Específico'] = raw_amostra['categoria_google']
                df_amostra_final['Nota Google'] = raw_amostra['nota']
                df_amostra_final['Qtd Avaliações'] = raw_amostra['avaliacoes']
                df_amostra_final['Endereço Completo'] = raw_amostra['endereco_completo']
                df_amostra_final['Bairro'] = raw_amostra['bairro']
                df_amostra_final['Cidade'] = raw_amostra['cidade']
                df_amostra_final['UF'] = raw_amostra['estado']
                df_amostra_final['Site'] = raw_amostra['site']
                
                buffer_amostra = io.BytesIO()
                with pd.ExcelWriter(buffer_amostra, engine='xlsxwriter') as writer_amostra:
                    df_amostra_final.to_excel(writer_amostra, index=False, sheet_name='Amostra')
                    worksheet = writer_amostra.sheets['Amostra']
                    worksheet.set_column('A:A', 30)
                    worksheet.set_column('D:D', 25)
                
                st.download_button(
                    label="🎁 BAIXAR AMOSTRA GRÁTIS (Top 5)",
                    data=buffer_amostra.getvalue(),
                    file_name="amostra_diskleads_top5.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Baixe 5 leads reais para testar a qualidade."
                )

            df_preview = pd.DataFrame()
            df_preview['Empresa'] = df_f['nome']
            df_preview['Telefone'] = df_f['telefone'].apply(lambda x: str(x)[:-4] + "****" if x and len(str(x)) > 4 else "****")
            df_preview['Link WhatsApp'] = df_f['tipo_contato'].apply(lambda x: "🔒 No Excel" if str(x) == "Celular" else "-")
            df_preview['Tipo'] = df_f['tipo_contato']
            df_preview['Setor'] = df_f['Segmento']
            df_preview['Cidade'] = df_f['cidade']
            df_preview['Nota'] = df_f['nota']
            
            st.dataframe(df_preview.head(50), use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("📊 Raio-X da Base Selecionada")
            g1, g2, g3 = st.columns(3)
            with g1: st.bar_chart(df_f['cidade'].value_counts().head(10), color="#2E66F1", horizontal=True)
            with g2: st.bar_chart(df_f['bairro'].value_counts().head(10), color="#2ecc71", horizontal=True)
            with g3: st.bar_chart(df_f['Segmento'].value_counts(), color="#f39c12", horizontal=True)

st.divider()
col_f1, col_f2 = st.columns(2)
with col_f1:
    st.markdown("#### 📞 Precisa de Ajuda?")
    st.markdown("Teve problemas? Fale com o suporte.")
    st.markdown(f"📧 **E-mail:** [suporte.diskleads@gmail.com](mailto:suporte.diskleads@gmail.com)")
    st.link_button("Falar no WhatsApp", "https://wa.me/5511963048466?text=Olá,%20preciso%20de%20ajuda%20com%20o%20DiskLeads")

with col_f2:
    st.markdown("#### ⚖️ Termos e Privacidade")
    st.caption("© 2025 DiskLeads - Todos os direitos reservados.")
    st.caption("CNPJ: 61.957.100/0001-03")

# # ==========================================
# # 🛠️ MODO DESENVOLVEDOR: TESTE DE EXCEL
# # ==========================================
# st.sidebar.divider()
# if st.sidebar.checkbox("🛠️ Ativar Modo Teste (Excel)"):
#     st.sidebar.warning("Modo de teste ativo. O botão abaixo gera a lista COMPLETA do filtro atual.")
#     if total_leads > 0:
#         # Mesma lógica de geração do arquivo pago
#         df_teste = pd.DataFrame()
#         df_teste['Empresa'] = df_f['nome']
#         df_teste['Tipo de Telefone'] = df_f['tipo_contato']
#         df_teste['Telefone'] = df_f['telefone']
#         df_teste['Link WhatsApp'] = df_f.apply(gerar_link_wa, axis=1)
#         df_teste['Atualizado em'] = df_f['data_fmt']
#         df_teste['Setor Principal'] = df_f['Segmento']
#         df_teste['Nicho Específico'] = df_f['categoria_google']
#         df_teste['Nota Google'] = df_f['nota']
#         df_teste['Qtd Avaliações'] = df_f['avaliacoes']
#         df_teste['Endereço Completo'] = df_f['endereco_completo']
#         df_teste['Bairro'] = df_f['bairro']
#         df_teste['Cidade'] = df_f['cidade']
#         df_teste['UF'] = df_f['estado']
#         df_teste['Site'] = df_f['site']

#         buffer_teste = io.BytesIO()
#         with pd.ExcelWriter(buffer_teste, engine='xlsxwriter') as writer_teste:
#             df_teste.to_excel(writer_teste, index=False, sheet_name='Leads_Full')
#             worksheet = writer_teste.sheets['Leads_Full']
#             worksheet.set_column('A:A', 30)
#             worksheet.set_column('D:D', 25)

#         st.sidebar.download_button(
#             label="📥 BAIXAR LISTA COMPLETA (TESTE)",
#             data=buffer_teste.getvalue(),
#             file_name=f"TESTE_FULL_{total_leads}_leads.xlsx",
#             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#             type="primary",
#             use_container_width=True
#         )
#     else:
#         st.sidebar.info("Selecione um filtro com resultados para testar o Excel.")