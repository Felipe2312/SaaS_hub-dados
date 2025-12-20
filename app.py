import streamlit as st
import pandas as pd
from supabase import create_client
import io
import mercadopago
import time
import os
from datetime import datetime

# ==========================================
# 🔐 CONFIGURAÇÕES E CREDENCIAIS
# ==========================================
st.set_page_config(page_title="DiskLeads", layout="wide", page_icon="🚀")

try:
    SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["supabase"]["url"]
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets["supabase"]["key"]
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN") or st.secrets["mercado_pago"]["access_token"]
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
    if any(x in cat for x in ['restaurante', 'pizzaria', 'hamburgueria', 'lanchonete', 'padaria']): return "Alimentação"
    if any(x in cat for x in ['médic', 'clinica', 'saúde', 'hospital', 'dentista']): return "Clínicas & Saúde"
    if any(x in cat for x in ['oficina', 'mecânic', 'auto', 'carro']): return "Automotivo"
    if any(x in cat for x in ['advoga', 'jurídic', 'lei', 'contabilidade']): return "Jurídico & Escritórios"
    if any(x in cat for x in ['loja', 'varejo', 'comércio', 'moda']): return "Varejo & Comércio"
    if any(x in cat for x in ['imobili', 'construtor', 'engenharia']): return "Construção & Imóveis"
    return "Outros"

def fmt_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def classificar_telefone_global(tel):
    """Classifica o telefone e filtra lixo."""
    if not tel: return "Outro"
    nums = "".join(filter(str.isdigit, str(tel)))
    
    if nums.startswith("55"):
        # Regra: 3º digito não pode ser 0 (DDD invalido)
        if len(nums) > 2 and nums[2] == '0': return "Outro"
        if len(nums) == 13 and nums[4] == '9': return "Celular"
        elif len(nums) == 12: return "Fixo"
    else:
        if nums.startswith("0"): return "Outro"
        if len(nums) == 11 and nums[2] == '9': return "Celular"
        elif len(nums) == 10: return "Fixo"
            
    return "Outro"

def calcular_preco(qtd):
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
    
    # Ancoragem em R$ 0,35
    preco_ancora_ref = 0.35
    valor_ancora = qtd * preco_ancora_ref
    
    if preco_unitario >= 0.35:
        pct_economia_total = 0
    else:
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
        # Garantindo que campos existam
        if 'categoria_google' not in df.columns: df['categoria_google'] = 'Outros'
        df['categoria_google'] = df['categoria_google'].fillna('Não identificada')
        
        df['Segmento'] = df['categoria_google'].apply(normalizar_categoria)
        
        # Tratamento de Data
        if 'data_extracao' in df.columns:
            df['data_temp'] = pd.to_datetime(df['data_extracao'], errors='coerce')
            df['Data Atualização'] = df['data_temp'].dt.strftime('%d/%m/%Y').fillna(datetime.today().strftime('%d/%m/%Y'))
        else:
            df['Data Atualização'] = datetime.today().strftime('%d/%m/%Y')

        # Classificação de Telefone
        df['tipo_contato'] = df['telefone'].apply(classificar_telefone_global)
        
        # Filtro de Qualidade
        df = df[df['tipo_contato'].isin(['Celular', 'Fixo'])]
        
    return df

# ==========================================
# 🖥️ HEADER
# ==========================================
df_raw = get_all_data()

st.title(f"🚀 {NOME_MARCA}")
st.markdown("### A plataforma de inteligência de dados locais.")
st.caption("Enriqueça seu CRM com dados públicos, atualizados e validados do Google Maps.")

with st.expander("ℹ️ **O que eu vou receber e quanto custa?**", expanded=False):
    c_info1, c_info2 = st.columns([1.2, 1])
    with c_info1:
        st.markdown("#### 📦 O que vem no arquivo?")
        st.markdown("""
        * ✅ **Nome da Empresa**
        * ✅ **Telefone** (Móvel ou Misto) + **Link WhatsApp**
        * ✅ **Endereço Completo** (Rua, Bairro, Cidade, UF)
        * ✅ **Website** e Link do Google Maps
        * ✅ **Data de Atualização** (Para garantir dados frescos)
        """)
    with c_info2:
        st.markdown("#### 💲 Tabela de Preços")
        st.markdown("""
        | Qtd | Preço/Lead |
        | :--- | :--- |
        | < 200 | **R$ 0,35** |
        | > 200 | **R$ 0,25** |
        | > 1k | **R$ 0,15** |
        | > 5k | **R$ 0,08** |
        """)

st.divider()

# ==========================================
# 🔍 FILTROS (LÓGICA HIERÁRQUICA)
# ==========================================
with st.container(border=True):
    st.subheader("🛠️ Configure sua Lista")
    
    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    with c1: busca_nome = st.text_input("Buscar por Nome", placeholder="Ex: Silva...")
    with c2: nota_range = st.select_slider("Nota Google", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
    with c3: filtro_site = st.radio("Site?", ["Todos", "Sim", "Não"], horizontal=True)
    with c4: filtro_tel = st.radio("Telefone", ["Todos", "Só Celular", "Só Fixo"], horizontal=True)

    t1, t2 = st.tabs(["🎯 Segmentação", "📍 Localização"])

    with t1:
        col_a, col_b = st.columns(2)
        with col_a:
            opts_macro = sorted(df_raw['Segmento'].unique()) if not df_raw.empty else []
            f_macro = st.multiselect("Setor Principal", opts_macro)
        with col_b:
            if f_macro: df_nicho_opts = df_raw[df_raw['Segmento'].isin(f_macro)]
            else: df_nicho_opts = df_raw
            opts_nicho = sorted(df_nicho_opts['categoria_google'].unique()) if not df_nicho_opts.empty else []
            f_google = st.multiselect("Nicho Específico", opts_nicho)

    with t2:
        col_d, col_e, col_f = st.columns(3)
        opts_uf = sorted(df_raw['estado'].unique()) if not df_raw.empty else []
        with col_d: f_uf = st.multiselect("Estado (UF)", opts_uf)
        
        if f_uf: df_cid_opts = df_raw[df_raw['estado'].isin(f_uf)]
        else: df_cid_opts = df_raw
        opts_cidade = sorted(df_cid_opts['cidade'].unique()) if not df_cid_opts.empty else []
        with col_e: f_cidade = st.multiselect("Cidade", opts_cidade)
        
        if f_cidade: df_bai_opts = df_cid_opts[df_cid_opts['cidade'].isin(f_cidade)]
        else: df_bai_opts = df_cid_opts
        opts_bairro = sorted(df_bai_opts['bairro'].unique()) if not df_bai_opts.empty else []
        with col_f: f_bairro = st.multiselect("Bairro", opts_bairro)

# --- APLICAÇÃO DOS FILTROS ---
df_f = df_raw.copy()

if busca_nome: df_f = df_f[df_f['nome'].str.contains(busca_nome, case=False, na=False)]
if filtro_site == "Sim": df_f = df_f[df_f['site'].notnull()]
elif filtro_site == "Não": df_f = df_f[df_f['site'].isnull()]
df_f = df_f[(df_f['nota'] >= nota_range[0]) & (df_f['nota'] <= nota_range[1])]

if filtro_tel == "Só Celular": df_f = df_f[df_f['tipo_contato'] == 'Celular']
elif filtro_tel == "Só Fixo": df_f = df_f[df_f['tipo_contato'] == 'Fixo']

if f_macro: df_f = df_f[df_f['Segmento'].isin(f_macro)]
if f_google: df_f = df_f[df_f['categoria_google'].isin(f_google)]
if f_uf: df_f = df_f[df_f['estado'].isin(f_uf)]
if f_cidade: df_f = df_f[df_f['cidade'].isin(f_cidade)]
if f_bairro: df_f = df_f[df_f['bairro'].isin(f_bairro)]

# ==========================================
# 🚦 DASHBOARD
# ==========================================

filtros_ativos = any([busca_nome, f_macro, f_google, f_uf, f_cidade, f_bairro])

if not filtros_ativos:
    st.info("👆 Utilize os filtros para começar.")
    m1, m2, m3 = st.columns(3)
    with m1: st.metric("Empresas", f"{len(df_raw):,}".replace(",", "."))
    with m2: st.metric("Cidades", f"{df_raw['cidade'].nunique()}")
    with m3: st.metric("Setores", f"{df_raw['Segmento'].nunique()}")
    if 'Data Atualização' in df_raw.columns and not df_raw.empty:
        st.caption(f"📅 Base atualizada até: **{df_raw['Data Atualização'].max()}**")
    st.markdown("---")

else:
    total_leads = len(df_f)
    resumo_preco = calcular_preco(total_leads)
    valor_total = round(resumo_preco['total'], 2)

    st.divider()

    if total_leads == 0:
        st.warning("⚠️ Nenhum lead encontrado com essa combinação.")
    else:
        # Preço
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                st.caption("Volume")
                st.markdown(f"### {total_leads:,}".replace(",", "."))
            with c2:
                st.caption("Preço/Unid")
                st.markdown(f"### {fmt_real(resumo_preco['unitario'])}")
            with c3:
                st.caption("Total")
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
                faltam = resumo_preco['prox_qtd'] - total_leads
                st.info(f"💡Adicione **{faltam} leads** para pagar **{fmt_real(resumo_preco['prox_preco'])}/unid**.")

        # Pagamento
        if 'ref_venda' not in st.session_state:
            st.session_state.ref_venda = f"REF_{int(time.time())}"

        check_banco = supabase.table("vendas").select("*").eq("external_reference", st.session_state.ref_venda).execute()
        dados_venda = check_banco.data[0] if check_banco.data else None
        pago = True if (dados_venda and dados_venda['status'] == 'pago') else False

        if pago:
            st.balloons()
            st.success(f"✅ Pagamento Confirmado! Enviado para {dados_venda['email_cliente']}")
            
            # Botão Download Pós-Venda
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Recriar excel limpo (simplificado aqui pois o user ja tem o link)
                df_f.to_excel(writer, index=False)
            st.download_button("💾 Baixar Arquivo", output.getvalue(), f"leads_{st.session_state.ref_venda}.xlsx", use_container_width=True)
            
            if st.button("🔄 Nova Busca"):
                st.session_state.clear()
                st.rerun()
        else:
            with st.container(border=True):
                st.subheader("📬 Finalizar Compra")
                ce1, ce2 = st.columns(2)
                with ce1: email_input = st.text_input("Seu E-mail", placeholder="seu@email.com")
                with ce2: email_confirm = st.text_input("Confirme seu E-mail", placeholder="seu@email.com")
                
                if email_input and email_confirm and (email_input != email_confirm):
                    st.warning("⚠️ Os e-mails não coincidem.")

                pode_prosseguir = (email_input == email_confirm) and ("@" in email_input)

                if st.button("💳 IR PARA PAGAMENTO SEGURO", type="primary", use_container_width=True, disabled=not pode_prosseguir):
                    
                    # === 🛠️ CRIAÇÃO E LIMPEZA TOTAL DO EXCEL 🛠️ ===
                    df_export = df_f.copy()

                    # 1. Gerar Link WhatsApp
                    def gerar_link_wpp(row):
                        tel = str(row.get('telefone', ''))
                        tipo = str(row.get('tipo_contato', ''))
                        if tipo == "Celular": 
                            nums = "".join(filter(str.isdigit, tel))
                            if not nums.startswith("55"): nums = f"55{nums}"
                            return f"https://wa.me/{nums}"
                        return ""

                    df_export['Link WhatsApp'] = df_export.apply(gerar_link_wpp, axis=1)

                    # 2. MAPA DE LIMPEZA (De -> Para)
                    # Usei 'endereco_completo' pois é assim que geralmente vem do Supabase se for scraper.
                    # Se vier 'endereco', ajustaremos.
                    mapa_colunas = {
                        'nome': 'Empresa',
                        'telefone': 'Telefone',
                        'tipo_contato': 'Tipo Telefone',
                        'Link WhatsApp': 'Link WhatsApp',
                        'Data Atualização': 'Atualizado em',
                        'Segmento': 'Setor Principal',
                        'categoria_google': 'Nicho Específico',
                        'nota': 'Nota Google',
                        'site': 'Site',
                        'endereco_completo': 'Endereço Completo',
                        'bairro': 'Bairro',
                        'cidade': 'Cidade',
                        'estado': 'UF'
                    }

                    # 3. Renomear e Filtrar (Whitelist)
                    # Primeiro renomeia o que encontrar
                    df_export = df_export.rename(columns=mapa_colunas)
                    
                    # Define a ordem desejada das colunas FINAIS (já renomeadas)
                    ordem_final = [
                        'Empresa', 'Telefone', 'Tipo Telefone', 'Link WhatsApp', 
                        'Atualizado em', 'Setor Principal', 'Nicho Específico', 
                        'Nota Google', 'Site', 'Endereço Completo', 
                        'Bairro', 'Cidade', 'UF'
                    ]
                    
                    # Mantém APENAS o que estiver na ordem_final e que exista no DF
                    cols_finais = [c for c in ordem_final if c in df_export.columns]
                    df_export = df_export[cols_finais]

                    # 4. Gerar Arquivo
                    output_file = io.BytesIO()
                    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
                        df_export.to_excel(writer, index=False, sheet_name='Leads')
                        workbook = writer.book
                        worksheet = writer.sheets['Leads']
                        # Formatação
                        link_fmt = workbook.add_format({'font_color': 'blue', 'underline': True})
                        worksheet.set_column('A:A', 30) # Empresa
                        worksheet.set_column('B:C', 16) # Tel/Tipo
                        worksheet.set_column('D:D', 25) # Link Zap
                        worksheet.set_column('E:E', 12) # Data
                        worksheet.set_column('J:J', 40) # Endereço

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
                        "items": [{"title": f"Base {total_leads} Leads ({filtro_tel}) - {NOME_MARCA}", "quantity": 1, "unit_price": float(valor_total), "currency_id": "BRL"}],
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
                        st.error("Erro ao gerar link.")

                if 'link_ativo' in st.session_state:
                    st.info("🕒 Checkout aberto em nova guia.")
                    st.markdown(f'<div style="text-align:center;"><a href="{st.session_state.link_ativo}" target="_blank"><button style="padding:12px; background-color:#2e66f1; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">ABRIR PAGAMENTO</button></a></div>', unsafe_allow_html=True)
                    
                    with st.status("Aguardando confirmação...") as status:
                        for _ in range(60):
                            time.sleep(3)
                            check = supabase.table("vendas").select("status").eq("external_reference", st.session_state.ref_venda).execute()
                            if check.data and check.data[0]['status'] == 'pago':
                                status.update(label="✅ Pago!", state="complete")
                                st.rerun()

    # 3. Análise Visual (Prévia Mascarada)
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
    
    # Visualização segura (Mascarada)
    df_preview = df_f.head(50).copy()
    if 'telefone' in df_preview.columns:
        df_preview['telefone'] = df_preview['telefone'].apply(lambda x: str(x)[:-4] + "****" if x and len(str(x)) > 4 else "****")

    # Mapeamento para visualização na tela (Não afeta o Excel)
    colunas_tela = {
        'nome': 'Empresa', 'tipo_contato': 'Tipo', 'telefone': 'Telefone', 
        'Data Atualização': 'Atualizado em', 'Segmento': 'Setor', 
        'categoria_google': 'Nicho', 'bairro': 'Bairro', 'cidade': 'Cidade', 
        'estado': 'UF', 'nota': 'Nota'
    }
    cols_exists = [c for c in colunas_tela.keys() if c in df_preview.columns]
    
    st.dataframe(df_preview[cols_exists].rename(columns=colunas_tela), use_container_width=True, hide_index=True)