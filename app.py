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

# CSS Ajustado: Removemos o warning-box amarelo agressivo
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
    faixas = [
        {"limite": 300, "preco": 0.25},    
        {"limite": 1000, "preco": 0.15},
        {"limite": 3000, "preco": 0.10}, 
        {"limite": 5000, "preco": 0.06}, 
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
    preco_medio = total / qtd if qtd > 0 else 0.25
    valor_ancora = qtd * 0.25 
    pct_off = int(((valor_ancora - total) / valor_ancora) * 100) if valor_ancora > 0 else 0
    return {
        "unitario_medio": preco_medio,
        "total": total,
        "total_ancora": valor_ancora,
        "pct_off": pct_off,
        "prox_qtd": prox_meta,
        "prox_preco_marginal": prox_preco_meta
    }

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
        
        # Padronização de Colunas
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
            st.markdown("#### 📦 O que vem no arquivo?")
            st.markdown("""
            * ✅ **Nome da Empresa** e **Qtd. Avaliações**
            * ✅ **Telefone** (Validado) + **Link WhatsApp**
            * ✅ **Endereço Completo** (Rua, Bairro, Cidade, UF)
            * ✅ **Website** e Link do Google Maps
            * ✅ **Data de Atualização** (Dados Recentes)
            """)
        with c_info2:
            st.markdown("#### 📉 Descontos Progressivos")
            st.markdown("""
            | Faixa (Leads) | Preço Unitário |
            | :--- | :--- |
            | Primeiros 300 | **R$ 0,25** |
            | 301 a 1.000 | **R$ 0,15** |
            | 1.001 a 3.000 | **R$ 0,10** |
            | 3.001 a 5.000 | **R$ 0,06** |
            | + 5.000 | **R$ 0,04** |
            """)

    st.divider()

    df_raw = get_local_data()

    if df_raw.empty:
        st.warning("🔄 **Sincronizando Base de Dados...**")
        st.write("Estamos otimizando os arquivos no servidor. Aguarde 1 minuto e recarregue.")
        if st.button("🔄 Recarregar Página"): st.rerun()
    
    else:
        # --- FILTROS ---
        with st.container(border=True):
            st.subheader("🛠️ Configure sua Lista")
            c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 1, 1])
            
            with c1: busca_nome = st.text_input("Buscar Nome", placeholder="Ex: Padaria, Oficina...")
            with c2: nota_range = st.select_slider("Nota Mínima", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
            with c3: avaliacoes_range = st.slider("Qtd. Avaliações", 0, 5000, (0, 5000), step=10)
            with c4: filtro_site = st.radio("Site?", ["Todos", "Sim", "Não"], horizontal=True)
            with c5: filtro_tel = st.radio("Telefone", ["Todos", "Celular", "Fixo"], horizontal=True, index=0)

            t1, t2 = st.tabs(["🎯 Segmentação", "📍 Localização"])

            with t1:
                col_a, col_b = st.columns(2)
                with col_a:
                    opts_macro = sorted(df_raw['Segmento'].dropna().unique().astype(str).tolist())
                    f_macro = st.multiselect("Setor Principal", opts_macro, placeholder="Selecione setores...")
                with col_b:
                    if f_macro: df_nicho_opts = df_raw[df_raw['Segmento'].isin(f_macro)]
                    else: df_nicho_opts = df_raw
                    opts_nicho = sorted(df_nicho_opts['categoria_google'].dropna().unique().astype(str).tolist())
                    f_google = st.multiselect("Nicho Específico", opts_nicho, placeholder="Ex: Dentistas, Pet Shops...")

            with t2:
                col_d, col_e, col_f = st.columns(3)
                opts_uf = sorted(df_raw['estado'].dropna().unique().astype(str).tolist())
                with col_d: f_uf = st.multiselect("Estado (UF)", opts_uf, placeholder="Selecione...")
                
                if f_uf: df_cid_opts = df_raw[df_raw['estado'].isin(f_uf)]
                else: df_cid_opts = df_raw
                opts_cidade = sorted(df_cid_opts['cidade'].dropna().unique().astype(str).tolist())
                with col_e: f_cidade = st.multiselect("Cidade", opts_cidade, placeholder="Ex: Campinas...")
                
                if f_cidade: df_bai_opts = df_cid_opts[df_cid_opts['cidade'].isin(f_cidade)]
                else: df_bai_opts = df_cid_opts
                opts_bairro = sorted(df_bai_opts['bairro'].dropna().unique().astype(str).tolist())
                with col_f: f_bairro = st.multiselect("Bairro", opts_bairro, placeholder="Selecione...")

        # --- APLICAÇÃO DOS FILTROS ---
        df_f = df_raw.copy()

        if filtro_tel == "Celular":
            df_f = df_f[df_f['tipo_contato'] == 'Celular']
        elif filtro_tel == "Fixo":
            df_f = df_f[df_f['tipo_contato'] == 'Fixo']

        if busca_nome: df_f = df_f[df_f['nome'].str.contains(busca_nome, case=False, na=False)]
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
        filtros_ativos = any([busca_nome, f_macro, f_google, f_uf, f_cidade, f_bairro, filtro_aval_ativo])

        if not filtros_ativos:
            st.info("👆 Selecione um filtro para começar.")
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Empresas Disponíveis", f"{len(df_raw):,}".replace(",", "."))
            with m2: st.metric("Cidades", f"{df_raw['cidade'].nunique()}")
            with m3: st.metric("Setores", f"{df_raw['Segmento'].nunique()}")
            st.markdown("---")

        else:
            total_leads = len(df_f)
            resumo_preco = calcular_preco_final(total_leads)
            valor_total = round(resumo_preco['total'], 2)

            st.divider()

            if total_leads == 0:
                # --- DESIGN DE ZERO RESULTADOS (CLEAN) ---
                st.info("🔍 Nenhum resultado encontrado para esses filtros.")
                
                with st.container(border=True):
                    st.markdown("#### 🚀 Precisa desses dados específicos?")
                    st.caption("Nossa equipe pode minerar essa lista para você sob demanda com **25% de desconto**.")
                    msg_encomenda = "Olá, tentei buscar uma lista no site e não encontrei resultados. Gostaria de encomendar uma varredura personalizada com 25% de desconto."
                    st.link_button("Solicitar Varredura Personalizada", f"https://wa.me/5511963048466?text={msg_encomenda.replace(' ', '%20')}")

            else:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 1, 1])
                    with c1:
                        st.caption("Volume Selecionado")
                        st.markdown(f"### {total_leads:,}".replace(",", "."))
                        st.markdown(f"<span style='background-color:#2e66f1; color:white; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:bold;'>PROGRESSIVO</span>", unsafe_allow_html=True)
                    with c2:
                        st.caption("Preço Médio / Lead")
                        st.markdown(f"### {fmt_real(resumo_preco['unitario_medio'])}")
                    with c3:
                        st.caption("Total a Pagar")
                        st.markdown(f"<h3 style='color:#2ecc71; margin-top:0px'>{fmt_real(resumo_preco['total'])}</h3>", unsafe_allow_html=True)
                        if resumo_preco['pct_off'] > 0:
                            st.markdown(f"<span style='background-color: #d4edda; color: #155724; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold;'>-{resumo_preco['pct_off']}% OFF</span>", unsafe_allow_html=True)

                    if resumo_preco['prox_qtd']:
                        meta = resumo_preco['prox_qtd']
                        faltam = meta - total_leads
                        preco_futuro = resumo_preco['prox_preco_marginal']
                        st.write("")
                        st.progress(min(total_leads / meta, 0.95))
                        st.caption(f"💡 Falta pouco: Adicione mais **{faltam} leads** para pagar só **{fmt_real(preco_futuro)}** nos próximos!")
                    else:
                          st.success(f"💎 **Nível Atacado:** Você desbloqueou o menor preço do mercado!")

                # --- BANNER DE OPORTUNIDADE (DISCRETO) ---
                with st.container(border=True):
                    col_txt, col_btn = st.columns([3, 1])
                    with col_txt:
                        st.markdown("**🕵️ Procura algo mais específico?** Encomende uma varredura personalizada com **25% OFF**.")
                    with col_btn:
                        msg_banner = "Olá, encontrei alguns leads no site, mas queria encomendar uma lista maior/específica com o desconto de 25%."
                        st.link_button("Encomendar", f"https://wa.me/5511963048466?text={msg_banner.replace(' ', '%20')}", use_container_width=True)
                
                st.write("") 

                with st.container(border=True):
                    st.subheader("📬 Finalizar Compra")
                    ce1, ce2 = st.columns(2)
                    with ce1: email_input = st.text_input("Seu E-mail", placeholder="seu@email.com", help="Garante que você receba o arquivo.")
                    with ce2: email_confirm = st.text_input("Confirme seu E-mail", placeholder="seu@email.com")
                    
                    if email_input and email_confirm and (email_input != email_confirm):
                        st.warning("⚠️ Os e-mails não coincidem.")
                    
                    pode_prosseguir = (email_input == email_confirm) and ("@" in email_input)

                    if st.button("💳 IR PARA PAGAMENTO SEGURO", type="primary", use_container_width=True, disabled=not pode_prosseguir):
                        
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

                        supabase.table("vendas").upsert({
                            "external_reference": st.session_state.ref_venda,
                            "valor": valor_total,
                            "status": "pendente",
                            "email_cliente": email_input,
                            "url_arquivo": url_publica
                        }).execute()

                        pref_data = {
                            "items": [{"title": f"Base {total_leads} Leads - {NOME_MARCA}", "quantity": 1, "unit_price": float(valor_total), "currency_id": "BRL"}],
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
                            st.error("Erro no Mercado Pago.")

                    if 'link_ativo' in st.session_state:
                        st.info("🕒 Checkout aberto.")
                        st.markdown(f'<div style="text-align:center;"><a href="{st.session_state.link_ativo}" target="_blank"><button style="padding:12px; background-color:#2e66f1; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">ABRIR PAGAMENTO</button></a></div>', unsafe_allow_html=True)
                        
                        with st.status("Aguardando confirmação...") as status:
                            for _ in range(60):
                                time.sleep(3)
                                check = supabase.table("vendas").select("status").eq("external_reference", st.session_state.ref_venda).execute()
                                if check.data and check.data[0]['status'] == 'pago':
                                    status.update(label="✅ Pago!", state="complete")
                                    st.rerun()

            st.divider()
            st.subheader("📋 Amostra dos Dados (Top 5)")
            
            if total_leads > 0:
                st.markdown(" Quer validar antes? Baixe os **5 primeiros leads** completos agora.")
                
                # --- AMOSTRA GRÁTIS COM AS MESMAS COLUNAS DO PAGO ---
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

            # Preview na Tela
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