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
    .main .block-container {max-width: 960px; padding-top: 3rem; margin: auto;}
    .float:hover:after {
        content: "Precisa de ajuda?"; position: absolute; right: 70px; top: 15px;
        background: #333; color: white; padding: 5px 10px; border-radius: 5px;
        white-space: nowrap; font-size: 14px; box-shadow: 1px 1px 3px #888; pointer-events: none;
    }
    .box-encomenda {
        background-color: #f0f2f6; padding: 15px; border-radius: 10px;
        border-left: 5px solid #2E66F1; margin-bottom: 20px; margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 📞 BOTÃO FLUTUANTE ---
def setup_whatsapp_button():
    whatsapp_number = "5511963048466"
    whatsapp_message = "Olá, preciso de ajuda com o DiskLeads."
    st.markdown("""
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/font-awesome/4.5.0/css/font-awesome.min.css">
    <style>
    .float{
        position:fixed; width:60px; height:60px; bottom:40px; right:40px;
        background-color:#25d366; color:#FFF; border-radius:50px; text-align:center;
        font-size:30px; box-shadow: 2px 2px 3px #999; z-index:100;
        display:flex; align-items:center; justify-content:center;
        text-decoration:none; transition: all 0.3s ease;
    }
    .float:hover{ background-color:#128C7E; color:#FFF; transform: scale(1.1); }
    .my-float{ margin-top:0px; }
    </style>
    <a href="https://wa.me/%s?text=%s" class="float" target="_blank">
    <i class="fa fa-whatsapp my-float"></i>
    </a>
    """ % (whatsapp_number, whatsapp_message.replace(" ", "%20")), unsafe_allow_html=True)

setup_whatsapp_button()

# Conexão
try:
    SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["supabase"]["url"]
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets["supabase"]["key"]
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN") or st.secrets["mercado_pago"]["access_token"]
    NOME_MARCA = "DiskLeads"
except Exception as e:
    st.error("Erro config secrets.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
SDK = mercadopago.SDK(MP_ACCESS_TOKEN)

# --- 🕵️‍♂️ FUNÇÃO DE LOG (NOVIDADE) ---
def salvar_log(evento, detalhes):
    """Grava ações importantes no banco para entender o usuário."""
    try:
        supabase.table("logs_eventos").insert({
            "evento": evento,
            "detalhes": detalhes
        }).execute()
    except:
        pass # Se falhar o log, não trava o site

# --- FUNÇÕES AUXILIARES ---
def fmt_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_link_wa(row):
    if str(row['tipo_contato']) == "Celular":
        nums = "".join(filter(str.isdigit, str(row['telefone'])))
        return f"https://wa.me/55{nums}"
    return None

def mascarar_telefone(tel):
    s = str(tel)
    nums = "".join(filter(str.isdigit, s))
    if len(nums) >= 10:
        ddd = nums[:2]
        prefixo = nums[2:4]
        return f"🔒 ({ddd}) {prefixo}**-****"
    if len(s) > 4: return "🔒 " + s[:5] + "****-****"
    return "🔒 ****-****"

def calcular_preco_final(qtd):
    faixas = [
        {"limite": 500, "preco": 0.18}, {"limite": 2000, "preco": 0.12},
        {"limite": 5000, "preco": 0.08}, {"limite": float('inf'), "preco": 0.04}
    ]
    total = 0; ultimo_limite = 0; prox_meta = None; prox_preco_meta = None
    for i, f in enumerate(faixas):
        if qtd > f["limite"]:
            total += (f["limite"] - ultimo_limite) * f["preco"]
            ultimo_limite = f["limite"]
        else:
            total += (qtd - ultimo_limite) * f["preco"]
            if i + 1 < len(faixas):
                prox_meta = f["limite"]; prox_preco_meta = faixas[i+1]["preco"]
            break
    preco_medio = total / qtd if qtd > 0 else 0.18
    valor_ancora = qtd * 0.18
    pct_off = int(((valor_ancora - total) / valor_ancora) * 100) if valor_ancora > 0 else 0
    return {"unitario_medio": preco_medio, "total": total, "total_ancora": valor_ancora, "pct_off": pct_off, "prox_qtd": prox_meta, "prox_preco_marginal": prox_preco_meta}

def render_encomenda_banner():
    with st.container(border=True):
        c_txt, c_btn = st.columns([3, 1])
        with c_txt:
            st.markdown("##### 🕵️ Procurando algo específico?")
            st.caption("Se achou poucos resultados ou quer uma cidade que não está aqui, encomende uma **Varredura Sob Medida**.")
        with c_btn:
            msg_banner = "Olá, fiz uma busca no site mas gostaria de encomendar uma lista específica."
            st.link_button("Encomendar Lista", f"https://wa.me/5511963048466?text={msg_banner.replace(' ', '%20')}", use_container_width=True)

# --- DATA LOADER ---
CACHE_FILE = "data/leads.parquet"
@st.cache_data(ttl=86400, show_spinner=False)
def get_local_data():
    if not os.path.exists(CACHE_FILE): return pd.DataFrame()
    try:
        df = pd.read_parquet(CACHE_FILE)
        if 'segmento' in df.columns: df.rename(columns={'segmento': 'Segmento'}, inplace=True)
        if 'data_extracao' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['data_extracao']):
                df['data_extracao'] = pd.to_datetime(df['data_extracao'], errors='coerce')
            df['data_fmt'] = df['data_extracao'].dt.strftime('%d/%m/%Y').fillna(datetime.today().strftime('%d/%m/%Y'))
        else: df['data_fmt'] = datetime.today().strftime('%d/%m/%Y')
        
        cols_ordenacao, asc_ordenacao = [], []
        if 'data_extracao' in df.columns: cols_ordenacao.append('data_extracao'); asc_ordenacao.append(False)
        if 'nome' in df.columns: cols_ordenacao.append('nome'); asc_ordenacao.append(True)
        if cols_ordenacao: df = df.sort_values(by=cols_ordenacao, ascending=asc_ordenacao)
        return df
    except: return pd.DataFrame()

# ==========================================
# 🚀 APP START
# ==========================================
if 'ref_venda' not in st.session_state: st.session_state.ref_venda = f"REF_{int(time.time())}"
if 'mostrar_checkout' not in st.session_state: st.session_state.mostrar_checkout = False 

st.title(f"🚀 {NOME_MARCA}")

check_banco = supabase.table("vendas").select("*").eq("external_reference", st.session_state.ref_venda).execute()
is_pago = check_banco.data and check_banco.data[0]['status'] == 'pago'

if is_pago:
    st.balloons()
    st.success("✅ **PAGAMENTO CONFIRMADO!**")
    st.info("Baixe seu arquivo abaixo.")
    nome_arquivo = f"{st.session_state.ref_venda}.xlsx"
    try:
        arquivo_bin = supabase.storage.from_('leads_pedidos').download(nome_arquivo)
        c_down1, c_down2 = st.columns([2, 1])
        with c_down1:
            st.download_button("📥 BAIXAR MINHA PLANILHA", data=arquivo_bin, file_name=f"leads_{st.session_state.ref_venda}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)
        with c_down2:
            if st.button("🔄 Nova Busca", use_container_width=True):
                st.session_state.clear(); st.rerun()
    except: st.error("Erro ao recuperar arquivo.")

else:
    st.markdown("### A plataforma de inteligência de dados locais.")
    st.caption("Enriqueça seu CRM com dados públicos, atualizados e validados do Google Maps.")
    st.info("💡 **Como usar:** 1. Filtre pelo seu Nicho e Cidade > 2. Valide os 3 primeiros leads > 3. Desbloqueie a lista completa.")

    with st.spinner("🔄 Conectando ao Banco de Dados de Leads..."):
        df_raw = get_local_data()

    if df_raw.empty:
        st.warning("🔄 **Sincronizando Base de Dados...**")
        if st.button("🔄 Recarregar Página"): st.rerun()
    
    else:
        with st.container(border=True):
            st.subheader("🛠️ Configure sua Lista")
            c2, c3, c4, c5 = st.columns([1.5, 1.5, 1, 1])
            with c2: nota_range = st.select_slider("⭐ Nota Mínima", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
            with c3: avaliacoes_range = st.slider("🗣️ Qtd. Avaliações", 0, 5000, (0, 5000), step=10)
            with c4: filtro_site = st.radio("🌐 Tem Site?", ["Todos", "Sim", "Não"], horizontal=True)
            with c5: filtro_tel = st.radio("📞 Telefone", ["Todos", "Celular", "Fixo"], horizontal=True, index=0)
            st.divider()

            df_step1 = df_raw.copy()
            if filtro_site == "Sim": df_step1 = df_step1[df_step1['site'].notnull()]
            elif filtro_site == "Não": df_step1 = df_step1[df_step1['site'].isnull()]
            if filtro_tel == "Celular": df_step1 = df_step1[df_step1['tipo_contato'] == 'Celular']
            elif filtro_tel == "Fixo": df_step1 = df_step1[df_step1['tipo_contato'] == 'Fixo']
            
            df_step1['nota'] = pd.to_numeric(df_step1['nota'], errors='coerce').fillna(0)
            df_step1 = df_step1[(df_step1['nota'] >= nota_range[0]) & (df_step1['nota'] <= nota_range[1])]
            
            df_step1['avaliacoes'] = pd.to_numeric(df_step1['avaliacoes'], errors='coerce').fillna(0)
            min_aval, max_aval = avaliacoes_range
            if max_aval < 5000: df_step1 = df_step1[(df_step1['avaliacoes'] >= min_aval) & (df_step1['avaliacoes'] <= max_aval)]
            else: df_step1 = df_step1[df_step1['avaliacoes'] >= min_aval]

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

            # --- LOG DE BUSCA VAZIA (CENÁRIO PEDRA) ---
            if total_leads == 0:
                # Otimização: Só loga se não tiver logado isso nesta sessão ainda (para evitar spam)
                if 'last_log' not in st.session_state or st.session_state.last_log != f"zero_{len(f_cidade)}_{len(f_macro)}":
                    desc_log = f"Macro: {f_macro} | Google: {f_google} | Cidade: {f_cidade}"
                    salvar_log("busca_vazia", desc_log)
                    st.session_state.last_log = f"zero_{len(f_cidade)}_{len(f_macro)}"

                st.info("🔍 Nenhum resultado encontrado para essa combinação específica.")
                render_encomenda_banner()

            else:
                c_title, c_tip = st.columns([1.5, 1])
                with c_title: st.markdown(f"### ✅ Encontramos **{total_leads} Leads**")
                with c_tip:
                    if filtro_tel != "Celular": st.info("💡 **Dica:** Quer apenas contatos com WhatsApp? Suba e mude o filtro de Telefone para **'Celular'**.")

                def fmt_endereco(row):
                    end = str(row['endereco_completo']).split(',')[0]; bairro = str(row['bairro'])
                    return f"{end} - {bairro}" if bairro and bairro != 'nan' else end

                if not is_pago:
                    df_free = df_f.head(3).copy()
                    df_free['Empresa'] = df_free['nome']; df_free['Telefone'] = df_free['telefone']
                    df_free['WhatsApp'] = df_free.apply(gerar_link_wa, axis=1)
                    df_free['Endereço'] = df_free.apply(fmt_endereco, axis=1)
                    df_free['Cidade'] = df_free['cidade'].astype(str) + "-" + df_free['estado'].astype(str)
                    df_free['Nota'] = df_free['nota']; df_free['Atualizado'] = df_free['data_fmt']

                    df_locked_preview = df_f.iloc[3:10].copy()
                    if not df_locked_preview.empty:
                        df_locked_preview['Empresa'] = df_locked_preview['nome']
                        df_locked_preview['Telefone'] = df_locked_preview['telefone'].apply(mascarar_telefone)
                        df_locked_preview['WhatsApp'] = None
                        def mascara_end_row(row): return f"Rua Bloqueada*** - {str(row['bairro'])}"
                        df_locked_preview['Endereço'] = df_locked_preview.apply(mascara_end_row, axis=1)
                        df_locked_preview['Cidade'] = df_locked_preview['cidade'].astype(str) + "-" + df_locked_preview['estado'].astype(str)
                        df_locked_preview['Nota'] = df_locked_preview['nota']; df_locked_preview['Atualizado'] = df_locked_preview['data_fmt']
                        df_final_show = pd.concat([df_free, df_locked_preview], ignore_index=True)
                    else: df_final_show = df_free
                else:
                    df_full = df_f.head(100).copy()
                    df_full['Empresa'] = df_full['nome']; df_full['Telefone'] = df_full['telefone']
                    df_full['WhatsApp'] = df_full.apply(gerar_link_wa, axis=1)
                    df_full['Endereço'] = df_full.apply(fmt_endereco, axis=1)
                    df_full['Cidade'] = df_full['cidade'].astype(str) + "-" + df_full['estado'].astype(str)
                    df_full['Nota'] = df_full['nota']; df_full['Atualizado'] = df_full['data_fmt']
                    df_final_show = df_full

                df_final_show = df_final_show[['Empresa', 'Telefone', 'WhatsApp', 'Endereço', 'Cidade', 'Nota', 'Atualizado']]

                if not is_pago: st.success("💡A tabela abaixo é apenas uma amostra simplificada. A lista final desbloqueada contém colunas completas como **Endereço, Site e Nota Detalhada**.")

                qtd_linhas = len(df_final_show); altura_calc = (qtd_linhas + 1) * 35; altura_final = 500 if altura_calc > 500 else int(altura_calc)
                st.dataframe(df_final_show, use_container_width=True, hide_index=True, height=altura_final, column_config={
                        "Empresa": st.column_config.TextColumn("Empresa", width="medium"),
                        "Telefone": st.column_config.TextColumn("Telefone", width="small"),
                        "WhatsApp": st.column_config.LinkColumn("Ação", display_text="📲 Chamar", validate="^https://", width="small"),
                        "Endereço": st.column_config.TextColumn("Endereço Completo", width="medium"),
                        "Cidade": st.column_config.TextColumn("Cidade", width="small"),
                        "Nota": st.column_config.NumberColumn("Nota", format="%.1f ⭐", width="small"),
                        "Atualizado": st.column_config.TextColumn("Atualização", width="small")
                    })

                if not st.session_state.mostrar_checkout and not is_pago:
                    c_action1, c_action2, c_action3 = st.columns([1, 2, 1])
                    with c_action2:
                        st.write("")
                        if st.button(f"🔓 DESBLOQUEAR LISTA COMPLETA", type="primary", use_container_width=True):
                            
                            # --- LOG DE CLIQUE NO BOTÃO (CENÁRIO BRONZE) ---
                            desc_log = f"Total: {total_leads} | Filtros: {f_macro} / {f_cidade}"
                            salvar_log("clique_desbloquear", desc_log)
                            
                            st.session_state.mostrar_checkout = True
                            st.rerun()
                
                elif st.session_state.mostrar_checkout and not is_pago:
                    st.divider()
                    st.markdown("### 💰 Finalizar Pedido")
                    
                    start_idx, end_idx = 0, total_leads
                    qtd_selecionada = total_leads
                    
                    if total_leads > 50:
                        with st.container(border=True):
                            st.markdown("##### 💸 O preço ficou alto? Ajuste para o seu bolso.")
                            st.caption("Não precisa comprar tudo de uma vez. Reduza a quantidade abaixo até o valor ficar confortável para você.")
                            faixa_escolhida = st.slider("Intervalo de Leads", min_value=0, max_value=total_leads, value=(0, total_leads), step=10, help="Use as duas bolinhas para escolher o início e o fim da sua lista.")
                            start_idx, end_idx = faixa_escolhida
                            qtd_selecionada = end_idx - start_idx
                            if qtd_selecionada <= 0: st.warning("⚠️ Selecione pelo menos 1 lead."); st.stop()
                            if start_idx > 0: st.info(f"⏭️ Pulando os primeiros **{start_idx}** leads. Você vai levar do nº {start_idx+1} ao {end_idx}.")

                    resumo_preco = calcular_preco_final(qtd_selecionada)
                    valor_total = round(resumo_preco['total'], 2)

                    with st.container(border=True):
                        c1, c2, c3 = st.columns([1, 1, 1.3])
                        with c1: st.metric("Qtd. Selecionada", f"{qtd_selecionada}")
                        with c2: st.metric("Preço por Lead", fmt_real(resumo_preco['unitario_medio']))
                        with c3:
                            if resumo_preco['pct_off'] > 0:
                                st.markdown(f"<p style='margin-bottom: -5px; color: #888; font-size: 14px;'><s>{fmt_real(resumo_preco['total_ancora'])}</s></p><h2 style='color: #2ecc71; margin-top: 0px;'>{fmt_real(valor_total)}</h2>", unsafe_allow_html=True)
                                st.caption(f"Economia de {resumo_preco['pct_off']}% aplicada.")
                            else: st.metric("Valor Total", fmt_real(valor_total))
                        
                        prox_meta = resumo_preco.get('prox_qtd')
                        if prox_meta:
                            falta_para_meta = prox_meta - qtd_selecionada
                            if 0 < falta_para_meta <= 500:
                                novo_preco = resumo_preco.get('prox_preco_marginal')
                                st.info(f"📉 **Quer pagar menos?** Adicione mais **{falta_para_meta}** leads para o preço cair para **{fmt_real(novo_preco)}** por lead!")

                        st.subheader("📬 Dados para Recebimento")
                        c_mail1, c_mail2 = st.columns([2, 1])
                        with c_mail1: email_input = st.text_input("Seu E-mail", placeholder="ex: joao@gmail.com")
                        with c_mail2: cupom_input = st.text_input("Cupom de Desconto", placeholder="Código").upper().strip()

                        fator_desconto, abatimento_fixo = 0.0, 0.0; msg_cupom, cupom_salvar = None, None
                        if cupom_input:
                            try:
                                res_c = supabase.table("cupons_validos").select("*").eq("codigo", cupom_input).execute()
                                if res_c.data:
                                    c_info = res_c.data[0]; cupom_salvar = cupom_input
                                    abatimento_fixo = float(c_info['valor_abatimento_sinal'] or 0)
                                    if c_info['tipo_desconto'] == 'porcentagem':
                                        fator_desconto = float(c_info['valor_desconto']) / 100
                                        display_msg = f"{int(c_info['valor_desconto'])}% OFF"
                                    else:
                                        desconto_reais = float(c_info['valor_desconto'])
                                        fator_desconto = desconto_reais / valor_total if valor_total > 0 else 0
                                        display_msg = f"{fmt_real(desconto_reais)} OFF"
                                    msg_cupom = f"✅ Cupom aplicado ({display_msg})!"; 
                                    if abatimento_fixo > 0: msg_cupom += f" + {fmt_real(abatimento_fixo)} abatido."
                                else: msg_cupom = "❌ Cupom inválido."
                            except: msg_cupom = "❌ Erro validação."

                        valor_final_pagar = (valor_total * (1 - fator_desconto)) - abatimento_fixo
                        if valor_final_pagar < 0: valor_final_pagar = 0.0
                        if msg_cupom: st.info(msg_cupom)

                        pode_prosseguir = email_input and ("@" in email_input) and (qtd_selecionada > 0)
                        
                        st.write("")
                        if st.button(f"💳 PAGAR {fmt_real(valor_final_pagar)} E BAIXAR", type="primary", use_container_width=True, disabled=not pode_prosseguir):
                            
                            df_f_cut = df_f.iloc[start_idx:end_idx].copy() 
                            lista_filtros = []
                            if f_macro: lista_filtros.append(f"Setor: {', '.join(f_macro)}")
                            if f_cidade: lista_filtros.append(f"Cidade: {', '.join(f_cidade)}")
                            lista_filtros.append(f"Pacote: {qtd_selecionada} Leads (Índice {start_idx} a {end_idx})")
                            resumo_filtros_str = " | ".join(lista_filtros) if lista_filtros else "Filtros Personalizados"

                            df_final = pd.DataFrame()
                            df_final['Empresa'] = df_f_cut['nome']; df_final['Tipo de Telefone'] = df_f_cut['tipo_contato']
                            df_final['Telefone'] = df_f_cut['telefone']; df_final['Link WhatsApp'] = df_f_cut.apply(gerar_link_wa, axis=1)
                            df_final['Atualizado em'] = df_f_cut['data_fmt']; df_final['Setor Principal'] = df_f_cut['Segmento']
                            df_final['Nicho Específico'] = df_f_cut['categoria_google']; df_final['Nota Google'] = df_f_cut['nota']
                            df_final['Qtd Avaliações'] = df_f_cut['avaliacoes']; df_final['Endereço Completo'] = df_f_cut['endereco_completo']
                            df_final['Bairro'] = df_f_cut['bairro']; df_final['Cidade'] = df_f_cut['cidade']
                            df_final['UF'] = df_f_cut['estado']; df_final['Site'] = df_f_cut['site']
                            
                            output_file = io.BytesIO()
                            with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
                                df_final.to_excel(writer, index=False, sheet_name='Leads')
                                worksheet = writer.sheets['Leads']; worksheet.set_column('A:A', 30); worksheet.set_column('D:D', 25)
                            
                            nome_arquivo = f"{st.session_state.ref_venda}.xlsx"
                            supabase.storage.from_('leads_pedidos').upload(path=nome_arquivo, file=output_file.getvalue(), file_options={"x-upsert": "true", "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
                            url_publica = supabase.storage.from_('leads_pedidos').get_public_url(nome_arquivo)

                            dados_venda = {
                                "external_reference": st.session_state.ref_venda, "valor": valor_final_pagar, "status": "pendente",
                                "email_cliente": email_input, "url_arquivo": url_publica, "detalhes_filtro": resumo_filtros_str, "cupom": cupom_salvar
                            }
                            supabase.table("vendas").upsert(dados_venda, on_conflict="external_reference").execute()

                            preco_mp = float(valor_final_pagar)
                            if preco_mp < 0.1: preco_mp = 0.1
                            pref_data = {
                                "items": [{"title": f"Pack {qtd_selecionada} Leads - {NOME_MARCA}", "quantity": 1, "unit_price": preco_mp, "currency_id": "BRL"}],
                                "external_reference": st.session_state.ref_venda, "back_urls": {"success": "https://leads-brasil.streamlit.app/"}, "auto_return": "approved"
                            }
                            res = SDK.preference().create(pref_data)
                            if res["status"] in [200, 201]: st.session_state.link_ativo = res["response"]["init_point"]; st.rerun()
                            else: st.error("Erro no Mercado Pago.")

                    if 'link_ativo' in st.session_state:
                         st.markdown(f'<div style="text-align:center; margin-top:10px;"><a href="{st.session_state.link_ativo}" target="_blank"><button style="padding:15px; width:100%; background-color:#28a745; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold; font-size:18px;">✅ CLIQUE PARA PAGAR</button></a></div>', unsafe_allow_html=True)
                         with st.status("Aguardando pagamento...") as status:
                            for _ in range(60):
                                time.sleep(3)
                                check = supabase.table("vendas").select("status").eq("external_reference", st.session_state.ref_venda).execute()
                                if check.data and check.data[0]['status'] == 'pago': status.update(label="Pago!", state="complete"); st.rerun()
                            status.update(label="Tempo esgotado. Verifique se pagou.", state="error")
                         if st.button("Já paguei (Atualizar)"): st.rerun()

                st.write("")
                render_encomenda_banner()

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