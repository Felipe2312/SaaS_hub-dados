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
# 🔐 CONFIGURAÇÕES
# ==========================================
st.set_page_config(page_title="DiskLeads", layout="wide", page_icon="🚀")

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

try:
    SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["supabase"]["url"]
    SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets["supabase"]["key"]
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN") or st.secrets["mercado_pago"]["access_token"]
    NOME_MARCA = "DiskLeads"
except Exception as e:
    st.error("Erro: Verifique se todos os secrets estão configurados corretamente.")
    st.stop()

# Clientes
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
SDK = mercadopago.SDK(MP_ACCESS_TOKEN)

# ==========================================
# 🧠 FUNÇÕES
# ==========================================

# ==========================================
# 🧠 FUNÇÃO DE AGRUPAMENTO (NORMALIZAÇÃO) AVANÇADA
# ==========================================
# ==========================================
# 🧠 FUNÇÃO DE AGRUPAMENTO V3.0 (Data-Driven)
# ==========================================
# ==========================================
# 🧠 FUNÇÃO DE AGRUPAMENTO V4.0 (Refinada)
# ==========================================
def normalizar_categoria(cat_google):
    if not cat_google or str(cat_google).strip() == "" or str(cat_google).lower() == "não identificada":
        return "Não Identificada / Outros"
    
    # Normalização básica
    cat = str(cat_google).lower().replace('-', ' ').replace('/', ' ')

    # -----------------------------------------------------------
    # 1. SAÚDE, VETERINÁRIA & BEM-ESTAR
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'médic', 'clinic', 'clínica', 'hospital', 'saúde', 'dentista', 'odonto', 'ortodon',
        'terapia', 'terapeuta', 'psicól', 'psiquiatra', 'fisiotera', 'nutri', 'laboratório', 
        'farmá', 'farmacêutica', 'drogaria', 'ambulatório', 'pronto atendimento', 'bem estar',
        'ótica', 'ortoped', 'pediatra', 'dermatolog', 'cardiolog', 'oftalmo', 'quiroprax',
        'veterinári', 'pet', 'animal', 'banho e tosa', 'acupunt', 'urologista', 'ginecolog',
        'obstetra', 'cirurgi', 'enfermeir', 'diagnóst', 'vacina', 'raio x', 'podólogo', 
        'massoterapeuta', 'fonoaudi', 'radiolog', 'repouso', 'clínico geral'
    ]): return "Saúde & Veterinária"

    # -----------------------------------------------------------
    # 2. BELEZA E ESTÉTICA
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'beleza', 'estétic', 'esteticista', 'salão', 'cabeleireiro', 'barbearia', 'manicure', 
        'pedicure', 'unha', 'sobrancelha', 'cílios', 'depila', 'massagem', 'spa',
        'cosmétic', 'perfumaria', 'maquiagem', 'tatuagem', 'piercing', 'capilar', 'sex shop'
    ]): return "Beleza & Estética"

    # -----------------------------------------------------------
    # 3. FITNESS E ESPORTES
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'academia', 'fit', 'gym', 'crossfit', 'pilates', 'yoga', 'artes marciais', 'condicionamento',
        'esporte', 'natação', 'personal', 'treinamento', 'suplemento', 'clube',
        'futebol', 'quadra', 'bicicleta', 'ciclis'
    ]): return "Fitness & Esportes"

    # -----------------------------------------------------------
    # 4. ALIMENTAÇÃO E BEBIDAS
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'restaurante', 'bar', 'lanchonete', 'pizzaria', 'hamburgueria', 'sushi', 'pizza',
        'japonês', 'churrascaria', 'padaria', 'confeitaria', 'café', 'cafeteria', 'esfiharia',
        'bistrô', 'buffet', 'açaí', 'sorvete', 'doceria', 'bolo', 'mercado', 'gastropub',
        'supermercado', 'mercearia', 'hortifruti', 'adega', 'bebida', 'food', 'laticínios',
        'vinícola', 'verdureiro', 'frutaria', 'açougue', 'acougue', 'peixaria', 'cesta',
        'água', 'agua', 'natural', 'naturais', 'empório', 'gourmet', 'cerveja', 'sacolão',
        'catering', 'aliment', 'delivery', 'cachorro', 'quente', 'sanduicheria', 'diner'
    ]): return "Alimentação & Bebidas"

    # -----------------------------------------------------------
    # 5. CONSTRUÇÃO, CASA E MANUTENÇÃO
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'constru', 'obra', 'engenhar', 'engenheiro', 'arquitet', 'reform', 'pintor', 'pintura', 
        'elétric', 'eletricista', 'encanador', 'marceneiro', 'marcenaria', 'vidraçaria', 'vidraceiro', 
        'serral', 'marmoraria', 'móve', 'moveis', 'decora', 'design de interior', 'piscina', 
        'ar condicionado', 'climatização', 'refrigeração', 'material', 'ferragens', 'tinta', 'piso', 
        'madeira', 'madeireira', 'gás', 'jardin', 'paisagismo', 'chaveiro', 'mudança', 'dedetizadora', 
        'poço', 'colch', 'sofá', 'sofa', 'ferramenta', 'hidráulic', 'terraplenagem', 'tapeçaria', 
        'telhado', 'calha', 'gesso', 'cimento', 'esquadria', 'bombeiro', 'conserto', 'reparo', 
        'manutenção', 'instalação', 'faxina', 'limpeza', 'solar', 'energia', 'carpin', 'empreiteira',
        'desentupidora', 'aquecedor', 'saneamento', 'apartamento', 'terreno', 'loteamento', 'residencial'
    ]): return "Construção, Casa & Manutenção"

    # -----------------------------------------------------------
    # 6. AUTOMOTIVO E TRANSPORTES
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'auto', 'carro', 'veículo', 'moto', 'mecânic', 'oficina', 'pneu', 'borracharia',
        'funilaria', 'pintura automotiva', 'posto', 'combustível', 'estacionamento',
        'concessionária', 'aluguel', 'transporte', 'frete', 'guincho', 'martelinho', 'reboque',
        'lava', 'lavagem', 'estética automotiva', 'aeroporto', 'ônibus', 'táxi', 'logística',
        'óleo', 'lubrificante', 'escapamento', 'bateria', 'rodas', 'balanceamento', 'entrega', 'carga'
    ]): return "Automotivo & Transportes"

    # -----------------------------------------------------------
    # 7. MODA E VESTUÁRIO (Atualizado com Joias)
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'roupa', 'moda', 'vestuário', 'calcado', 'calçado', 'sapato', 'tênis', 'sapateiro',
        'acessório', 'joia', 'bijuteria', 'bolsa', 'infantil', 'bebe', 'noiva', 'ourives',
        'costur', 'alfaiate', 'uniforme', 'lingerie', 'mala', 'tecido', 'relojoaria', 'brechó',
        'joalher', 'joalheiro', 'ouro', 'butique'
    ]): return "Moda & Vestuário"

    # -----------------------------------------------------------
    # 8. COMÉRCIO VAREJISTA
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'papelaria', 'floricultura', 'presente', 'brinquedo', 'tabacaria', 'conveniência',
        'variedades', 'departamento', 'shopping', 'eletrodoméstico', 'colchão', 'colchões',
        'artigos', 'utilidades', 'loja', 'varejista', 'comércio', 'copiadora', 'livraria', 
        'banca', 'bazar', 'armarinho', 'artesanato', 'antiquário', 'outlet'
    ]): return "Comércio & Varejo"

    # -----------------------------------------------------------
    # 9. SERVIÇOS EMPRESARIAIS & GOVERNO (B2B)
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'advoga', 'jurídic', 'lei', 'contabil', 'contad', 'consultor', 'agência', 'assessoria',
        'marketing', 'publicidade', 'design', 'gráfic', 'impress', 'seguro', 'rh', 'relação',
        'imobili', 'corretor', 'coworking', 'escritório', 'financeir', 'banco', 'fórum',
        'empréstimo', 'consórcio', 'terceiriza', 'segurança', 'recrutamento', 'portaria',
        'cartório', 'despachante', 'agente', 'associa', 'remessa', 'administrat', 'escrituração',
        'prefeitura', 'pública', 'público', 'correios', 'tabelião', 'notaria', 'faixa', 'placa',
        'editora', 'fotó', 'foto', 'gravação'
    ]): return "Serviços B2B & Escritórios"

    # -----------------------------------------------------------
    # 10. EDUCAÇÃO E ENSINO
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'escola', 'colégio', 'faculdade', 'universidade', 'curso', 'idiomas', 'aula',
        'inglês', 'ensino', 'educação', 'treinamento', 'creche', 'berçário', 'aprendizagem',
        'autoescola', 'música', 'dança', 'biblioteca', 'jardim de infância', 'educacional'
    ]): return "Educação & Ensino"

    # -----------------------------------------------------------
    # 11. TECNOLOGIA E INFORMÁTICA
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'informática', 'computador', 'celular', 'smartphone', 'assistência técnica', 'telefonia',
        'software', 'ti ', 'tecnologia', 'internet', 'telecom', 'eletrônic', 'game',
        'lan house', 'cyber'
    ]): return "Tecnologia & Informática"

    # -----------------------------------------------------------
    # 12. TURISMO E LAZER
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'hotel', 'pousada', 'hostel', 'hospedaria', 'viagem', 'turismo', 'evento', 'festa',
        'casamento', 'formatura', 'produtora', 'show', 'teatro', 'cinema', 'noturna',
        'museu', 'parque', 'camping', 'acampamento', 'recreação', 'motel', 'atração', 'pesca'
    ]): return "Turismo & Lazer"

    # -----------------------------------------------------------
    # 13. INDÚSTRIA E AGRONEGÓCIO
    # -----------------------------------------------------------
    if any(x in cat for x in [
        'indústria', 'industrial', 'fábrica', 'fabricante', 'confecção', 'metalúrgica', 'siderúrgica', 
        'distribui', 'atacado', 'atacadista', 'fornecedor', 'agro', 'fazenda', 'sítio', 'pecuária',
        'rural', 'máquina', 'equipamento', 'usina', 'viveiro', 'planta', 'abatedouro', 'fundição',
        'produção', 'embalagem', 'plástico', 'aço', 'ferro', 'alumínio', 'armazém', 'depósito',
        'químic', 'tijolo', 'iluminação', 'cerâmica', 'vidro', 'tornearia', 'solda', 'mineração'
    ]): return "Indústria & Agronegócio"

    # Se sobrou algo muito genérico
    return "Outros Comércios & Serviços"

def fmt_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def classificar_telefone_global(tel):
    if not tel: return "Outro"
    nums = "".join(filter(str.isdigit, str(tel)))
    if nums.startswith("55"):
        if len(nums) > 2 and nums[2] == '0': return "Outro"
        if len(nums) == 13 and nums[4] == '9': return "Celular"
        elif len(nums) == 12: return "Fixo"
    else:
        if nums.startswith("0"): return "Outro"
        if len(nums) == 11 and nums[2] == '9': return "Celular"
        elif len(nums) == 10: return "Fixo"
    return "Outro"

# --- LÓGICA DE PREÇO (Corrigida para R$ 0,04 no final) ---
def calcular_preco_final(qtd):
    faixas = [
        {"limite": 200, "preco": 0.35},
        {"limite": 500, "preco": 0.25},
        {"limite": 1000, "preco": 0.15},
        {"limite": 2000, "preco": 0.10},
        {"limite": 4000, "preco": 0.06},  # Volume Alto
        {"limite": float('inf'), "preco": 0.04} # Atacado Real (Acima de 4k)
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
            
    preco_medio = total / qtd if qtd > 0 else 0.35
    valor_ancora = qtd * 0.35 
    pct_off = int(((valor_ancora - total) / valor_ancora) * 100) if valor_ancora > 0 else 0

    return {
        "unitario_medio": preco_medio,
        "total": total,
        "total_ancora": valor_ancora,
        "pct_off": pct_off,
        "prox_qtd": prox_meta,
        "prox_preco_marginal": prox_preco_meta
    }

# CACHE DE 24 HORAS
@st.cache_data(ttl=86400)
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
        
        if 'avaliacoes' in df.columns:
            df['avaliacoes'] = pd.to_numeric(df['avaliacoes'].astype(str).str.replace('.', '', regex=False), errors='coerce').fillna(0).astype(int)
        else:
            df['avaliacoes'] = 0
            
        df['bairro'] = df['bairro'].fillna('Não informado')
        df['estado'] = df['estado'].fillna('N/A')
        if 'categoria_google' not in df.columns: df['categoria_google'] = 'Outros'
        df['categoria_google'] = df['categoria_google'].fillna('Não identificada')
        
        df['Segmento'] = df['categoria_google'].apply(normalizar_categoria)
        
        # 1. CLASSIFICA
        df['tipo_contato'] = df['telefone'].apply(classificar_telefone_global)
        
        if 'data_extracao' in df.columns:
            df['data_obj'] = pd.to_datetime(df['data_extracao'], errors='coerce')
            df['data_fmt'] = df['data_obj'].dt.strftime('%d/%m/%Y').fillna(datetime.today().strftime('%d/%m/%Y'))
        else:
            df['data_fmt'] = datetime.today().strftime('%d/%m/%Y')
        
        # 2. LIMPA (FILTRA) AGORA MESMO
        # Tudo que não for Celular ou Fixo morre aqui e não entra no app.
        df = df[df['tipo_contato'].isin(['Celular', 'Fixo'])]
        
    return df

# ==========================================
# 🖥️ UX: RENDERIZA O SITE
# ==========================================

st.title(f"🚀 {NOME_MARCA}")
st.markdown("### A plataforma de inteligência de dados locais.")
st.caption("Enriqueça seu CRM com dados públicos, atualizados e validados do Google Maps.")

# --- TABELA DE PREÇOS (Atualizada para mostrar o tier de 0.04) ---
with st.expander("ℹ️ **Entenda o nosso Modelo de Economia**", expanded=False):
    c_info1, c_info2 = st.columns([1.2, 1])
    with c_info1:
        st.markdown("#### 📦 O que vem no arquivo?")
        st.markdown("""
        * ✅ **Nome da Empresa** e **Qtd. Avaliações**
        * ✅ **Telefone** (Móvel ou Misto) + **Link WhatsApp**
        * ✅ **Endereço Completo** (Rua, Bairro, Cidade, UF)
        * ✅ **Website** e Link do Google Maps
        * ✅ **Data de Atualização** (Dados Recentes)
        """)
    with c_info2:
        st.markdown("#### 📉 Descontos Rápidos")
        st.info("Quanto mais você compra, maior o desconto nos leads excedentes.")
        st.markdown("""
        | Faixa (Novos Leads) | Preço Marginal |
        | :--- | :--- |
        | Primeiros 200 | **R$ 0,35** |
        | 201 a 500 | **R$ 0,25** |
        | 501 a 1.000 | **R$ 0,15** |
        | 1.001 a 2.000 | **R$ 0,10** |
        | 2.001 a 4.000 | **R$ 0,06** |
        | + 4.000 | **R$ 0,04** |
        """)

st.divider()

# ==========================================
# 📥 CARREGAMENTO DE DADOS (JÁ LIMPOS)
# ==========================================
with st.spinner("🔄 Conectando ao servidor seguro e baixando dados... Aguarde um instante."):
    # df_raw já vem sem lixo (telefones inválidos já foram removidos)
    df_raw = get_all_data()

# --- FILTROS ---
with st.container(border=True):
    st.subheader("🛠️ Configure sua Lista")
    c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 1, 1])
    
    with c1: busca_nome = st.text_input("Buscar Nome", placeholder="Ex: Silva...")
    with c2: nota_range = st.select_slider("Nota Mínima", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
    with c3: avaliacoes_range = st.slider("Qtd. Avaliações", 0, 1000, (0, 1000), help="Filtre pela quantidade de reviews.")
    with c4: filtro_site = st.radio("Site?", ["Todos", "Sim", "Não"], horizontal=True)
    with c5: filtro_tel = st.radio("Telefone", ["Todos (Móvel/Fixo)", "Apenas Celular", "Apenas Fixo"], horizontal=True, index=0)

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

# --- APPLY FILTROS ---
df_f = df_raw.copy()

if filtro_tel == "Apenas Celular":
    df_f = df_f[df_f['tipo_contato'] == 'Celular']
elif filtro_tel == "Apenas Fixo":
    df_f = df_f[df_f['tipo_contato'] == 'Fixo']

if busca_nome: df_f = df_f[df_f['nome'].str.contains(busca_nome, case=False, na=False)]
if filtro_site == "Sim": df_f = df_f[df_f['site'].notnull()]
elif filtro_site == "Não": df_f = df_f[df_f['site'].isnull()]

df_f = df_f[(df_f['nota'] >= nota_range[0]) & (df_f['nota'] <= nota_range[1])]

min_aval, max_aval = avaliacoes_range
if max_aval == 1000:
    df_f = df_f[df_f['avaliacoes'] >= min_aval]
else:
    df_f = df_f[(df_f['avaliacoes'] >= min_aval) & (df_f['avaliacoes'] <= max_aval)]

if f_macro: df_f = df_f[df_f['Segmento'].isin(f_macro)]
if f_google: df_f = df_f[df_f['categoria_google'].isin(f_google)]
if f_uf: df_f = df_f[df_f['estado'].isin(f_uf)]
if f_cidade: df_f = df_f[df_f['cidade'].isin(f_cidade)]
if f_bairro: df_f = df_f[df_f['bairro'].isin(f_bairro)]

filtro_aval_ativo = (avaliacoes_range[0] > 0) or (avaliacoes_range[1] < 1000)
filtros_ativos = any([busca_nome, f_macro, f_google, f_uf, f_cidade, f_bairro, filtro_aval_ativo])

if not filtros_ativos:
    st.info("👆 Selecione um filtro para começar.")
    m1, m2, m3 = st.columns(3)
    with m1: st.metric("Empresas Válidas", f"{len(df_raw):,}".replace(",", "."))
    with m2: st.metric("Cidades", f"{df_raw['cidade'].nunique()}")
    with m3: st.metric("Setores", f"{df_raw['Segmento'].nunique()}")
    st.markdown("---")

else:
    total_leads = len(df_f)
    resumo_preco = calcular_preco_final(total_leads)
    valor_total = round(resumo_preco['total'], 2)

    st.divider()

    if total_leads == 0:
        st.warning("⚠️ Nenhum lead encontrado com os filtros selecionados.")
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
                if resumo_preco['pct_off'] > 0:
                      st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="text-decoration: line-through; color: #ff4b4b; font-size: 14px;">{fmt_real(resumo_preco['total_ancora'])}</span>
                        <span style="background-color: #d4edda; color: #155724; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: bold;">-{resumo_preco['pct_off']}% OFF</span>
                    </div>""", unsafe_allow_html=True)
                st.markdown(f"<h3 style='color:#2ecc71; margin-top:0px'>{fmt_real(resumo_preco['total'])}</h3>", unsafe_allow_html=True)

            # --- DICA DE UPGRADE SINCRONIZADA ---
            if resumo_preco['prox_qtd']:
                meta = resumo_preco['prox_qtd']
                faltam = meta - total_leads
                preco_futuro = resumo_preco['prox_preco_marginal']
                
                # Barra ajustada para o novo tier de 4000
                faixas_limites = [0, 200, 500, 1000, 2000, 4000]
                limite_anterior = 0
                for L in faixas_limites:
                    if total_leads >= L: limite_anterior = L
                    else: break
                
                denominador = meta - limite_anterior
                numerador = total_leads - limite_anterior
                progresso = min(numerador / denominador, 0.95) if denominador > 0 else 0
                
                st.write("")
                st.progress(progresso)
                
                st.info(f"""
                💡 **Falta pouco:** Adicione mais **{faltam} leads** para que os próximos custem apenas **{fmt_real(preco_futuro)}** cada!
                """)
            else:
                 st.success(f"💎 **Nível Atacado:** Você desbloqueou o menor preço do mercado ({fmt_real(0.04)}/lead nos adicionais)!")

        # ==========================================
        # 💳 PAGAMENTO & DOWNLOAD
        # ==========================================
        if 'ref_venda' not in st.session_state:
            st.session_state.ref_venda = f"REF_{int(time.time())}"

        check_banco = supabase.table("vendas").select("*").eq("external_reference", st.session_state.ref_venda).execute()
        is_pago = check_banco.data and check_banco.data[0]['status'] == 'pago'

        if is_pago:
            st.balloons()
            
            df_final_down = pd.DataFrame()
            df_final_down['Empresa'] = df_f['nome']
            df_final_down['Telefone'] = df_f['telefone']
            df_final_down['Tipo de Telefone'] = df_f['tipo_contato']
            
            def gerar_link_down(row):
                if row['tipo_contato'] == "Celular":
                    nums = "".join(filter(str.isdigit, str(row['telefone'])))
                    if not nums.startswith("55"): nums = f"55{nums}"
                    return f"https://wa.me/{nums}"
                return ""
            df_final_down['Link WhatsApp'] = df_f.apply(gerar_link_down, axis=1)
            
            df_final_down['Atualizado em'] = df_f['data_fmt']
            df_final_down['Setor Principal'] = df_f['Segmento']
            df_final_down['Nicho Específico'] = df_f['categoria_google']
            df_final_down['Nota Google'] = df_f['nota']
            df_final_down['Qtd Avaliações'] = df_f['avaliacoes']
            df_final_down['Endereço Completo'] = df_f['endereco_completo']
            df_final_down['Bairro'] = df_f['bairro']
            df_final_down['Cidade'] = df_f['cidade']
            df_final_down['UF'] = df_f['estado']
            df_final_down['Site'] = df_f['site']

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_final_down.to_excel(writer, index=False, sheet_name='Leads')
                worksheet = writer.sheets['Leads']
                worksheet.set_column('A:A', 30)
                worksheet.set_column('D:D', 25)
            
            st.success("✅ Pagamento Confirmado com Sucesso!")
            
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.download_button(
                    label="💾 BAIXAR PLANILHA AGORA",
                    data=output.getvalue(),
                    file_name=f"leads_{st.session_state.ref_venda}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            with col_d2:
                if st.button("🔄 Fazer Nova Busca", use_container_width=True):
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
                    
                    df_final = pd.DataFrame()
                    df_final['Empresa'] = df_f['nome']
                    df_final['Telefone'] = df_f['telefone']
                    df_final['Tipo de Telefone'] = df_f['tipo_contato']
                    
                    def gerar_link(row):
                        if row['tipo_contato'] == "Celular":
                            nums = "".join(filter(str.isdigit, str(row['telefone'])))
                            if not nums.startswith("55"): nums = f"55{nums}"
                            return f"https://wa.me/{nums}"
                        return ""
                    df_final['Link WhatsApp'] = df_f.apply(gerar_link, axis=1)
                    
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

    # 3. Análise Visual
    st.divider()
    st.subheader("📊 Raio-X da Base Selecionada")
    g1, g2, g3 = st.columns(3)
    with g1: st.bar_chart(df_f['cidade'].value_counts().head(10), color="#2E66F1", horizontal=True)
    with g2: st.bar_chart(df_f['bairro'].value_counts().head(10), color="#2ecc71", horizontal=True)
    with g3: st.bar_chart(df_f['Segmento'].value_counts(), color="#f39c12", horizontal=True)

    st.subheader("📋 Amostra dos Dados (Top 50)")
    
    df_preview = pd.DataFrame()
    df_preview['Empresa'] = df_f['nome']
    df_preview['Telefone'] = df_f['telefone'].apply(lambda x: str(x)[:-4] + "****" if x and len(str(x)) > 4 else "****")
    df_preview['Tipo'] = df_f['tipo_contato']
    df_preview['Setor'] = df_f['Segmento']
    df_preview['Nicho'] = df_f['categoria_google']
    df_preview['Cidade'] = df_f['cidade']
    df_preview['Nota'] = df_f['nota']
    df_preview['Avaliações'] = df_f['avaliacoes']
    df_preview['Atualizado em'] = df_f['data_fmt']
    
    st.dataframe(df_preview.head(50), use_container_width=True, hide_index=True)

# ==========================================
# 🛡️ RODAPÉ E SUPORTE
# ==========================================
st.divider()
col_f1, col_f2 = st.columns(2)

with col_f1:
    st.markdown("#### 📞 Precisa de Ajuda?")
    st.markdown("Teve problemas com o pagamento ou download? Fale com o Felipe.")
    st.markdown(f"📧 **E-mail:** [suporte.diskleads@gmail.com](mailto:suporte.diskleads@gmail.com) | [feliperiosamaral@gmail.com](mailto:feliperiosamaral@gmail.com)")
    st.link_button("Falar no WhatsApp", "https://wa.me/5511963048466?text=Olá,%20preciso%20de%20ajuda%20com%20o%20DiskLeads")

with col_f2:
    st.markdown("#### ⚖️ Termos e Privacidade")
    with st.expander("Ler Aviso Legal (LGPD)"):
        st.caption("""
        **Origem dos Dados:** Todos os dados fornecidos nesta plataforma são extraídos de fontes públicas acessíveis via internet (Google Maps), conforme permitido pela legislação brasileira para fins de prospecção B2B.
        
        **Uso dos Dados:** Ao adquirir a lista, você se compromete a utilizar os dados de forma ética, respeitando as leis de proteção de dados (LGPD) e as regras de contato comercial (Não Perturbe).
        
        **Garantia:** Oferecemos os dados "como estão" nas fontes públicas. A taxa de assertividade média é de 80-90%.
        """)
    st.caption(f"© 2025 {NOME_MARCA} - Todos os direitos reservados.")
    st.caption(f"CNPJ: 61.957.100/0001-03")

# ==========================================
# 🛠️ DEBUGGER DE CATEGORIAS (Felipe)
# ==========================================
st.divider()
with st.expander("👨‍💻 Área Técnica (Diagnóstico de 'Outros')"):
    st.warning("Esta área serve para refinar o agrupamento. Copie a lista abaixo e mande para o Gemini.")
    
    # Pega apenas o que caiu na vala comum
    df_outros = df_raw[df_raw['Segmento'] == 'Outros Comércios & Serviços']
    
    if not df_outros.empty:
        # Conta a frequência de cada categoria perdida
        top_missed = df_outros['categoria_google'].value_counts().head(100).reset_index()
        top_missed.columns = ['Nome da Categoria no Google', 'Quantidade de Leads']
        
        c_debug1, c_debug2 = st.columns([2, 1])
        with c_debug1:
            st.dataframe(top_missed, height=400, use_container_width=True)
        with c_debug2:
            st.metric("Total em 'Outros'", f"{len(df_outros):,}".replace(",", "."))
            st.write("Copie os nomes da tabela ao lado que fazem sentido agrupar.")
    else:
        st.success("Nenhuma categoria 'Outros' encontrada! O filtro está perfeito.")