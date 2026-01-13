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

    /* CENTRALIZA E LIMITA A LARGURA EM MONITORES GRANDES */
    .main .block-container {
        max-width: 960px;
        padding-top: 3rem;
        margin: auto;
    }
    
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
    # Só gera link se for Celular. Se for fixo, retorna None
    if str(row['tipo_contato']) == "Celular":
        nums = "".join(filter(str.isdigit, str(row['telefone'])))
        return f"https://wa.me/55{nums}"
    return None

def mascarar_telefone(tel):
    """Adiciona cadeado, mantém DDD e mascara o resto."""
    s = str(tel)
    if len(s) > 4:
        return "🔒 " + s[:5] + "****-****"
    return "🔒 ****-****"

def calcular_preco_final(qtd):
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
# 🚀 LÓGICA DE FLUXO PRINCIPAL
# ==========================================

if 'ref_venda' not in st.session_state:
    st.session_state.ref_venda = f"REF_{int(time.time())}"

if 'mostrar_checkout' not in st.session_state:
    st.session_state.mostrar_checkout = False # Controla se mostra o PREÇO

check_banco = supabase.table("vendas").select("*").eq("external_reference", st.session_state.ref_venda).execute()
# Variável que controla a liberação dos dados
is_pago = check_banco.data and check_banco.data[0]['status'] == 'pago'

st.title(f"🚀 {NOME_MARCA}")

# -----------------------------------------------------------------
# CENÁRIO A: JÁ PAGO (TELA DE SUCESSO)
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
# CENÁRIO B: NÃO PAGO (FILTROS + PAYWALL)
# -----------------------------------------------------------------
else:
    st.markdown("### A plataforma de inteligência de dados locais.")
    st.caption("Enriqueça seu CRM com dados públicos, atualizados e validados do Google Maps.")
    st.info("💡 **Como usar:** 1. Filtre pelo seu Nicho e Cidade > 2. Valide as amostras na tela > 3. Desbloqueie a lista completa.")

    df_raw = get_local_data()

    if df_raw.empty:
        st.warning("🔄 **Sincronizando Base de Dados...**")
        st.write("Estamos otimizando os arquivos no servidor. Aguarde 1 minuto e recarregue.")
        if st.button("🔄 Recarregar Página"): st.rerun()
    
    else:
        # --- FILTROS ---
        with st.container(border=True):
            st.subheader("🛠️ Configure sua Lista")
            
            # Filtros Técnicos
            c2, c3, c4, c5 = st.columns([1.5, 1.5, 1, 1])
            with c2: nota_range = st.select_slider("⭐ Nota Mínima", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
            with c3: avaliacoes_range = st.slider("🗣️ Qtd. Avaliações", 0, 5000, (0, 5000), step=10)
            with c4: filtro_site = st.radio("🌐 Tem Site?", ["Todos", "Sim", "Não"], horizontal=True)
            with c5: filtro_tel = st.radio("📞 Telefone", ["Todos", "Celular", "Fixo"], horizontal=True, index=0)

            st.divider()

            # Prepara Cascata
            df_step1 = df_raw.copy()
            if filtro_site == "Sim": df_step1 = df_step1[df_step1['site'].notnull()]
            elif filtro_site == "Não": df_step1 = df_step1[df_step1['site'].isnull()]
            if filtro_tel == "Celular": df_step1 = df_step1[df_step1['tipo_contato'] == 'Celular']
            elif filtro_tel == "Fixo": df_step1 = df_step1[df_step1['tipo_contato'] == 'Fixo']
            
            df_step1['nota'] = pd.to_numeric(df_step1['nota'], errors='coerce').fillna(0)
            df_step1 = df_step1[(df_step1['nota'] >= nota_range[0]) & (df_step1['nota'] <= nota_range[1])]
            
            df_step1['avaliacoes'] = pd.to_numeric(df_step1['avaliacoes'], errors='coerce').fillna(0)
            min_aval, max_aval = avaliacoes_range
            if max_aval == 5000: df_step1 = df_step1[(df_step1['avaliacoes'] >= min_aval) & (df_step1['avaliacoes'] <= max_aval)]
            else: df_step1 = df_step1[df_step1['avaliacoes'] >= min_aval]

            # Abas de Seleção
            t1, t2 = st.tabs(["🎯 Segmentação (Obrigatório)", "📍 Localização (Opcional)"])
            f_macro, f_google, f_uf, f_cidade, f_bairro = [], [], [], [], []

            with t1:
                col_a, col_b = st.columns(2)
                with col_a:
                    opts_macro = sorted(df_step1['Segmento'].dropna().unique().astype(str).tolist())
                    f_macro = st.multiselect("Categoria Geral", opts_macro, placeholder="Ex: Saúde, Alimentação...")
                with col_b:
                    if f_macro: df_nicho_opts = df_step1[df_step1['Segmento'].isin(f_macro)]
                    else: df_nicho_opts = df_step1
                    opts_nicho = sorted(df_nicho_opts['categoria_google'].dropna().unique().astype(str).tolist())
                    f_google = st.multiselect("Atividade Específica (Google)", opts_nicho, placeholder="Ex: Cardiologista, Pizzaria...")

            df_step2 = df_step1.copy()
            if f_macro: df_step2 = df_step2[df_step2['Segmento'].isin(f_macro)]
            if f_google: df_step2 = df_step2[df_step2['categoria_google'].isin(f_google)]

            with t2:
                col_d, col_e, col_f = st.columns(3)
                with col_d:
                    opts_uf = sorted(df_step2['estado'].dropna().unique().astype(str).tolist())
                    f_uf = st.multiselect("Estado (UF)", opts_uf, placeholder="Selecione...")
                with col_e:
                    if f_uf: df_cid_opts = df_step2[df_step2['estado'].isin(f_uf)]
                    else: df_cid_opts = df_step2
                    opts_cidade = sorted(df_cid_opts['cidade'].dropna().unique().astype(str).tolist())
                    f_cidade = st.multiselect("Cidade", opts_cidade, placeholder="Ex: Campinas...")
                with col_f:
                    if f_cidade: df_bai_opts = df_cid_opts[df_cid_opts['cidade'].isin(f_cidade)]
                    else: df_bai_opts = df_cid_opts
                    opts_bairro = sorted(df_bai_opts['bairro'].dropna().unique().astype(str).tolist())
                    f_bairro = st.multiselect("Bairro", opts_bairro, placeholder="Selecione...")

        # --- APLICAÇÃO FINAL ---
        df_f = df_raw.copy()
        if filtro_tel == "Celular": df_f = df_f[df_f['tipo_contato'] == 'Celular']
        elif filtro_tel == "Fixo": df_f = df_f[df_f['tipo_contato'] == 'Fixo']
        if filtro_site == "Sim": df_f = df_f[df_f['site'].notnull()]
        elif filtro_site == "Não": df_f = df_f[df_f['site'].isnull()]

        df_f['nota'] = pd.to_numeric(df_f['nota'], errors='coerce').fillna(0)
        df_f = df_f[(df_f['nota'] >= nota_range[0]) & (df_f['nota'] <= nota_range[1])]

        df_f['avaliacoes'] = pd.to_numeric(df_f['avaliacoes'], errors='coerce').fillna(0)
        min_aval, max_aval = avaliacoes_range
        if max_aval == 5000: df_f = df_f[df_f['avaliacoes'] >= min_aval]
        else: df_f = df_f[(df_f['avaliacoes'] >= min_aval) & (df_f['avaliacoes'] <= max_aval)]

        if f_macro: df_f = df_f[df_f['Segmento'].isin(f_macro)]
        if f_google: df_f = df_f[df_f['categoria_google'].isin(f_google)]
        if f_uf: df_f = df_f[df_f['estado'].isin(f_uf)]
        if f_cidade: df_f = df_f[df_f['cidade'].isin(f_cidade)]
        if f_bairro: df_f = df_f[df_f['bairro'].isin(f_bairro)]

        filtro_aval_ativo = (avaliacoes_range[0] > 0) or (avaliacoes_range[1] < 5000)
        filtros_ativos = any([f_macro, f_google, f_uf, f_cidade, f_bairro, filtro_aval_ativo])

        if not filtros_ativos:
            st.info("👆 Selecione um filtro acima para começar a minerar.")
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Empresas Disponíveis", f"{len(df_raw):,}".replace(",", "."))
            with m2: st.metric("Cidades", f"{df_raw['cidade'].nunique()}")
            with m3: st.metric("Setores", f"{df_raw['Segmento'].nunique()}")
            st.markdown("---")
            render_encomenda_banner()

        else:
            total_leads = len(df_f)
            
            st.divider()

            if total_leads == 0:
                st.info("🔍 Nenhum resultado encontrado para essa combinação específica.")
                render_encomenda_banner()

            else:
                # =========================================================
                # 🔥 TABELA PREMIUM + PAYWALL
                # =========================================================
                
                # 1. Título e Dica Útil (CONDICIONAL)
                c_title, c_tip = st.columns([1.5, 1])
                with c_title:
                    st.markdown(f"### ✅ Encontramos **{total_leads} Leads**")
                with c_tip:
                    if filtro_tel != "Celular":
                        st.info("💡 **Dica:** Quer apenas contatos com WhatsApp? Suba e mude o filtro de Telefone para **'Celular'**.")

                # ---------------------------------------------------------
                # PREPARAÇÃO DOS DADOS
                # ---------------------------------------------------------
                
                def fmt_endereco(row):
                    end = str(row['endereco_completo']).split(',')[0] 
                    bairro = str(row['bairro'])
                    if bairro and bairro != 'nan': return f"{end} - {bairro}"
                    return end

                # ---------------------------------------------------------
                # PARTE A: OS 10 PRIMEIROS (GRÁTIS)
                # ---------------------------------------------------------
                df_view = df_f.head(10).copy()
                df_view['Empresa'] = df_view['nome'] 
                df_view['Telefone'] = df_view['telefone']
                df_view['WhatsApp'] = df_view.apply(gerar_link_wa, axis=1) # Link real
                df_view['Endereço'] = df_view.apply(fmt_endereco, axis=1)
                df_view['Cidade'] = df_view['cidade'].astype(str) + "-" + df_view['estado'].astype(str)
                df_view['Nota'] = df_view['nota']
                df_view['Atualizado'] = df_view['data_fmt']

                # ---------------------------------------------------------
                # PARTE B: BLOQUEADOS (AMOSTRA DE 5 APENAS)
                # ---------------------------------------------------------
                
                if not is_pago:
                    # Pega do 11º em diante, mas mostra SÓ MAIS 5 para não poluir
                    df_locked = df_f.iloc[10:].head(5).copy()
                    
                    if not df_locked.empty:
                        df_locked['Empresa'] = df_locked['nome'] 
                        df_locked['Telefone'] = df_locked['telefone'].apply(mascarar_telefone)
                        
                        # BLOQUEIO: None faz o botão sumir (o cadeado fica no telefone)
                        df_locked['WhatsApp'] = None 
                        
                        def mascara_end_row(row):
                            bairro = str(row['bairro'])
                            return f"Rua Bloqueada*** - {bairro}"
                        
                        df_locked['Endereço'] = df_locked.apply(mascara_end_row, axis=1)
                        df_locked['Cidade'] = df_locked['cidade'].astype(str) + "-" + df_locked['estado'].astype(str)
                        df_locked['Nota'] = df_locked['nota']
                        df_locked['Atualizado'] = df_locked['data_fmt']
                        
                        df_final_show = pd.concat([df_view, df_locked], ignore_index=True)
                    else:
                        df_final_show = df_view
                
                else:
                    # Se PAGOU, libera tudo (Top 100 para performance)
                    df_full = df_f.head(100).copy()
                    df_full['Empresa'] = df_full['nome']
                    df_full['Telefone'] = df_full['telefone']
                    df_full['WhatsApp'] = df_full.apply(gerar_link_wa, axis=1)
                    df_full['Endereço'] = df_full.apply(fmt_endereco, axis=1)
                    df_full['Cidade'] = df_full['cidade'].astype(str) + "-" + df_full['estado'].astype(str)
                    df_full['Nota'] = df_full['nota']
                    df_full['Atualizado'] = df_full['data_fmt']
                    df_final_show = df_full

                df_final_show = df_final_show[['Empresa', 'Telefone', 'WhatsApp', 'Endereço', 'Cidade', 'Nota', 'Atualizado']]

                # 4. RENDERIZA A TABELA NATIVA (Com Altura Dinâmica Corrigida)
                # Calcula altura: 35px por linha + cabeçalho. Trava em 500px.
                qtd_linhas = len(df_final_show)
                altura_calc = (qtd_linhas + 1) * 35 
                altura_final = 500 if altura_calc > 500 else int(altura_calc)

                st.dataframe(
                    df_final_show,
                    use_container_width=True,
                    hide_index=True,
                    height=altura_final,
                    column_config={
                        "Empresa": st.column_config.TextColumn("Empresa", width="medium"),
                        "Telefone": st.column_config.TextColumn("Telefone", width="small"),
                        "WhatsApp": st.column_config.LinkColumn(
                            "Ação",
                            display_text="📲 Chamar", 
                            validate="^https://",
                            width="small"
                        ),
                        "Endereço": st.column_config.TextColumn("Endereço Completo", width="medium"),
                        "Cidade": st.column_config.TextColumn("Cidade", width="small"),
                        "Nota": st.column_config.NumberColumn(
                            "Nota",
                            format="%.1f ⭐",
                            width="small"
                        ),
                        "Atualizado": st.column_config.TextColumn("Atualização", width="small")
                    }
                )

                # =========================================================
                # 🔓 BOTÃO DE DESBLOQUEIO E CHECKOUT
                # =========================================================
                
                # Se ainda não clicou para ver preço (e não pagou):
                if not st.session_state.mostrar_checkout and not is_pago:
                    c_action1, c_action2, c_action3 = st.columns([1, 2, 1])
                    with c_action2:
                        st.write("")
                        if st.button(f"🔓 DESBLOQUEAR LISTA COMPLETA ({total_leads} LEADS)", type="primary", use_container_width=True):
                            st.session_state.mostrar_checkout = True
                            st.rerun()
                
                # Se clicou para ver preço (ou já pagou e estamos mostrando o botão de sucesso):
                elif st.session_state.mostrar_checkout and not is_pago:
                    st.divider()
                    st.markdown("### 💰 Finalizar Pedido")
                    
                    resumo_preco = calcular_preco_final(total_leads)
                    valor_total = round(resumo_preco['total'], 2)

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([1, 1, 1.3])
                        with c1: st.metric("Total de Leads", f"{total_leads}")
                        with c2: st.metric("Preço por Lead", fmt_real(resumo_preco['unitario_medio']))
                        with c3:
                            if resumo_preco['pct_off'] > 0:
                                st.markdown(f"""
                                    <p style='margin-bottom: -5px; color: #888; font-size: 14px;'><s>{fmt_real(resumo_preco['total_ancora'])}</s></p>
                                    <h2 style='color: #2ecc71; margin-top: 0px;'>{fmt_real(valor_total)}</h2>
                                """, unsafe_allow_html=True)
                                st.caption(f"Economia de {resumo_preco['pct_off']}% aplicada.")
                            else:
                                st.metric("Valor Total", fmt_real(valor_total))

                        st.subheader("📬 Dados para Recebimento")
                        c_mail1, c_mail2 = st.columns([2, 1])
                        with c_mail1:
                            # CORREÇÃO: Removemos a confirmação de email
                            email_input = st.text_input("Seu E-mail", placeholder="ex: joao@gmail.com")
                        
                        with c_mail2:
                            cupom_input = st.text_input("Cupom de Desconto", placeholder="Código").upper().strip()

                        # Validação de Cupom
                        fator_desconto, abatimento_fixo = 0.0, 0.0
                        msg_cupom, cupom_salvar = None, None

                        if cupom_input:
                            try:
                                res_c = supabase.table("cupons_validos").select("*").eq("codigo", cupom_input).execute()
                                if res_c.data:
                                    c_info = res_c.data[0]
                                    cupom_salvar = cupom_input
                                    abatimento_fixo = float(c_info['valor_abatimento_sinal'] or 0)
                                    if c_info['tipo_desconto'] == 'porcentagem':
                                        fator_desconto = float(c_info['valor_desconto']) / 100
                                        display_msg = f"{int(c_info['valor_desconto'])}% OFF"
                                    else:
                                        desconto_reais = float(c_info['valor_desconto'])
                                        fator_desconto = desconto_reais / valor_total if valor_total > 0 else 0
                                        display_msg = f"{fmt_real(desconto_reais)} OFF"
                                    msg_cupom = f"✅ Cupom aplicado ({display_msg})!"
                                    if abatimento_fixo > 0: msg_cupom += f" + {fmt_real(abatimento_fixo)} abatido."
                                else: msg_cupom = "❌ Cupom inválido."
                            except: msg_cupom = "❌ Erro validação."

                        valor_final_pagar = (valor_total * (1 - fator_desconto)) - abatimento_fixo
                        if valor_final_pagar < 0: valor_final_pagar = 0.0
                        if msg_cupom: st.info(msg_cupom)

                        # Validação simplificada: só precisa ter @
                        pode_prosseguir = email_input and ("@" in email_input)
                        
                        st.write("")
                        if st.button(f"💳 PAGAR {fmt_real(valor_final_pagar)} E BAIXAR", type="primary", use_container_width=True, disabled=not pode_prosseguir):
                            
                            # --- PREPARAÇÃO DOS DADOS (EXCEL RICO RESTAURADO) ---
                            lista_filtros = []
                            if f_macro: lista_filtros.append(f"Setor: {', '.join(f_macro)}")
                            if f_cidade: lista_filtros.append(f"Cidade: {', '.join(f_cidade)}")
                            resumo_filtros_str = " | ".join(lista_filtros) if lista_filtros else "Filtros Personalizados"

                            # GERAÇÃO DO EXCEL COMPLETO (Premium)
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
                                worksheet.set_column('A:A', 30) # Empresa
                                worksheet.set_column('D:D', 25) # Link Zap
                            
                            nome_arquivo = f"{st.session_state.ref_venda}.xlsx"
                            supabase.storage.from_('leads_pedidos').upload(
                                path=nome_arquivo, 
                                file=output_file.getvalue(), 
                                file_options={"x-upsert": "true", "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
                            )
                            url_publica = supabase.storage.from_('leads_pedidos').get_public_url(nome_arquivo)

                            dados_venda = {
                                "external_reference": st.session_state.ref_venda,
                                "valor": valor_final_pagar,
                                "status": "pendente",
                                "email_cliente": email_input,
                                "url_arquivo": url_publica,
                                "detalhes_filtro": resumo_filtros_str,
                                "cupom": cupom_salvar
                            }
                            # CORREÇÃO CRÍTICA: on_conflict para evitar erro de duplicação
                            supabase.table("vendas").upsert(dados_venda, on_conflict="external_reference").execute()

                            # Mercado Pago
                            preco_mp = float(valor_final_pagar)
                            if preco_mp < 0.1: preco_mp = 0.1
                            
                            pref_data = {
                                "items": [{"title": f"Base {total_leads} Leads - {NOME_MARCA}", "quantity": 1, "unit_price": preco_mp, "currency_id": "BRL"}],
                                "external_reference": st.session_state.ref_venda,
                                "back_urls": {"success": "https://leads-brasil.streamlit.app/"},
                                "auto_return": "approved"
                            }
                            res = SDK.preference().create(pref_data)
                            
                            if res["status"] in [200, 201]:
                                st.session_state.link_ativo = res["response"]["init_point"]
                                st.rerun()
                            else: st.error("Erro no Mercado Pago.")

                    # Botão Link Ativo
                    if 'link_ativo' in st.session_state:
                         st.markdown(f'<div style="text-align:center; margin-top:10px;"><a href="{st.session_state.link_ativo}" target="_blank"><button style="padding:15px; width:100%; background-color:#28a745; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold; font-size:18px;">✅ CLIQUE PARA PAGAR</button></a></div>', unsafe_allow_html=True)
                         
                         with st.status("Aguardando pagamento...") as status:
                            for _ in range(60):
                                time.sleep(3)
                                check = supabase.table("vendas").select("status").eq("external_reference", st.session_state.ref_venda).execute()
                                if check.data and check.data[0]['status'] == 'pago':
                                    status.update(label="Pago!", state="complete")
                                    st.rerun()
                            status.update(label="Tempo esgotado. Verifique se pagou.", state="error")
                         
                         if st.button("Já paguei (Atualizar)"): st.rerun()

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
    