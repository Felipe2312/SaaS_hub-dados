import streamlit as st
import pandas as pd
from supabase import create_client
import io
import mercadopago
import time
import os
from datetime import datetime
import math
import re

# ==========================================
# 🔐 CONFIGURAÇÕES E ESTILO
# ==========================================
st.set_page_config(page_title="DiskLeads", layout="wide", page_icon="🚀")

# CSS para esconder elementos padrões e dar destaque ao botão flutuante
st.markdown("""
<style>
    .stDeployButton {display:none;}
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 20px;
        text-align: center;
        font-weight: bold;
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

# Conexão com Secrets (Híbrido: Funciona local e no Docker)
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

# ==========================================
# 🧠 INTELIGÊNCIA DE CATEGORIZAÇÃO (V11)
# ==========================================
CATEGORIAS_KEYWORDS = {
    "Saúde & Veterinária": [
        'médic', 'clinic', 'clínica', 'hospital', 'saúde', 'dentista', 'odonto', 'ortodon',
        'terapia', 'terapeuta', 'psicól', 'psiquiatra', 'psicanal', 'fisiotera', 'nutri', 
        'laboratório', 'farmá', 'farmacêutica', 'drogaria', 'ambulatório', 'pronto socorro', 
        'atendimento', 'bem estar', 'ótica', 'ortoped', 'pediatra', 'dermatolog', 'cardiolog', 
        'oftalmo', 'quiroprax', 'veterinári', 'pet', 'animal', 'banho e tosa', 'acupunt', 
        'urologista', 'ginecolog', 'obstetra', 'cirurgi', 'enfermeir', 'diagnóst', 'vacina', 
        'raio x', 'podólogo', 'massoterapeuta', 'fonoaudi', 'radiolog', 'repouso', 'clínico',
        'endocrino', 'gastro', 'otorrino', 'endodont', 'periodont', 'implante', 'osteopata',
        'ambulância', 'exame', 'queda de cabelo', 'optometrista', 'patologista', 'geriatra',
        'imunologista', 'oncologista', 'nefrologista', 'reumatologista', 'homeopatia', 'nutrólogo',
        'maternidade', 'diálise', 'enfermagem', 'naturopata', 'alergista', 'reflexologista',
        'reabilitação', 'ressonância', 'geriátrica', 'cuidados', 'dentário', 'dentadura',
        'prostodontista', 'médium', 'endoscopista', 'herbalista', 'interna', 'cirúrgico',
        'gestante', 'familia', 'paternidade', 'vacinação', 'sangue', 'medicina alternativa',
        'hematologista', 'meditação', 'melhor idade', 'hiv', 'aids', 'testagem'
    ],
    "Beleza & Estética": [
        'beleza', 'estétic', 'esteticista', 'salão', 'cabeleireiro', 'barbearia', 'manicure', 
        'pedicure', 'unha', 'sobrancelha', 'cílios', 'depila', 'massagem', 'spa', 'tatuador',
        'cosmétic', 'perfumaria', 'maquiagem', 'tatuagem', 'piercing', 'capilar', 'sex shop',
        'cabelereiro', 'remoção de tatuagens', 'estilista', 'hammam'
    ],
    "Fitness & Esportes": [
        'academia', 'fit', 'gym', 'crossfit', 'pilates', 'yoga', 'artes marciais', 'condicionamento',
        'esporte', 'esportivo', 'natação', 'personal', 'treinamento', 'suplemento', 'clube', 'mergulho',
        'futebol', 'quadra', 'bicicleta', 'ciclis', 'boliche', 'playground', 'skate', 'equitação',
        'kart', 'kartódromo', 'ginásio', 'poliesportivo', 'arena', 'adaptado'
    ],
    "Alimentação & Bebidas": [
        'restaurante', 'bar', 'lanchonete', 'pizzaria', 'hamburgueria', 'sushi', 'pizza',
        'japonês', 'churrascaria', 'padaria', 'confeitaria', 'café', 'cafeteria', 'esfiharia',
        'bistrô', 'buffet', 'açaí', 'sorvete', 'doceria', 'bolo', 'mercado', 'gastropub',
        'supermercado', 'mercearia', 'hortifruti', 'adega', 'bebida', 'food', 'laticínios',
        'vinícola', 'verdureiro', 'frutaria', 'açougue', 'acougue', 'peixaria', 'cesta',
        'água', 'agua', 'natural', 'naturais', 'empório', 'gourmet', 'cerveja', 'sacolão',
        'catering', 'aliment', 'delivery', 'cachorro', 'quente', 'sanduicheria', 'diner',
        'creperia', 'delicatessen', 'pub', 'charutaria', 'chocolate', 'patisserie', 
        'processamento de frutas', 'churrasco', 'chá', 'panificadora', 'charcutaria', 'frutas', 
        'churros', 'poke', 'saladas', 'cozinha solidária'
    ],
    "Construção, Casa & Manutenção": [
        'constru', 'obra', 'engenhar', 'engenheiro', 'arquitet', 'reform', 'pintor', 'pintura', 
        'elétric', 'eletricista', 'encanador', 'marceneiro', 'marcenaria', 'vidraçaria', 'vidraceiro', 
        'serral', 'marmoraria', 'móve', 'moveis', 'decora', 'design', 'piscina', 'pedreiro',
        'ar condicionado', 'climatização', 'refrigeração', 'material', 'ferragens', 'tinta', 'piso', 
        'madeira', 'madeireira', 'gás', 'jardin', 'paisagismo', 'chaveiro', 'mudança', 'dedetizadora', 
        'poço', 'colch', 'sofá', 'sofa', 'ferramenta', 'hidráulic', 'terraplenagem', 'tapeçaria', 
        'telhado', 'telhadista', 'calha', 'gesso', 'cimento', 'concreto', 'esquadria', 'bombeiro', 
        'conserto', 'reparo', 'manutenção', 'instalação', 'faxina', 'limpeza', 'solar', 'energia', 
        'carpin', 'empreiteira', 'caldeireiro', 'impermeabili', 'afiação', 'zeladoria', 'saneamento',
        'desentupidora', 'aquecedor', 'apartamento', 'terreno', 'loteamento', 'residencial', 'moradia',
        'antena', 'elevador', 'serralharia', 'ferreiro', 'entulho', 'caçamba', 'asfalto', 'coleta',
        'habitacional', 'restauração', 'revestimento', 'perfuração', 'edificações', 'guindaste', 
        'administração de propriedades', 'gestora de propriedade', 'faz tudo', 'doméstic', 'cercas',
        'séptico', 'incêndio', 'sistemas', 'aquecedor', 'chaves', 'cópia'
    ],
    "Automotivo & Transportes": [
        'auto', 'carro', 'veículo', 'moto', 'mecânic', 'oficina', 'pneu', 'borracharia',
        'funilaria', 'pintura automotiva', 'posto', 'combustível', 'estacionamento',
        'concessionária', 'aluguel', 'transporte', 'frete', 'guincho', 'martelinho', 'reboque',
        'lava', 'lavagem', 'estética automotiva', 'aeroporto', 'ônibus', 'táxi', 'logística',
        'óleo', 'lubrificante', 'escapamento', 'bateria', 'rodas', 'balanceamento', 'entrega', 'carga',
        'marina', 'barco', 'quadriciclo', 'empilhadeira', 'caminhão', 'valet', 'limusine', 'garagem',
        'pedágio', 'heliporto', 'aérea', 'decolagem', 'trailer'
    ],
    "Moda & Vestuário": [
        'roupa', 'moda', 'vestuário', 'calcado', 'calçado', 'sapato', 'tênis', 'sapateiro',
        'acessório', 'joia', 'bijuteria', 'bolsa', 'infantil', 'bebe', 'noiva', 'ourives',
        'costur', 'alfaiate', 'uniforme', 'lingerie', 'mala', 'tecido', 'relojoaria', 'brechó',
        'joalher', 'joalheiro', 'ouro', 'butique', 'bordado'
    ],
    "Comércio & Varejo": [
        'papelaria', 'floricultura', 'presente', 'brinquedo', 'tabacaria', 'conveniência',
        'variedades', 'departamento', 'shopping', 'eletrodoméstico', 'colchão', 'colchões',
        'artigos', 'utilidades', 'loja', 'varejista', 'comércio', 'copiadora', 'livraria', 
        'banca', 'bazar', 'armarinho', 'artesanato', 'antiquário', 'outlet', 'centro comercial',
        'sebo', 'videogame', 'smartshop', 'vídeo', 'lotérica', 'revistaria', 'quiosque', 'fraldas'
    ],
    "Serviços B2B & Escritórios": [
        'advoga', 'jurídic', 'lei', 'contabil', 'contad', 'consultor', 'agência', 'assessoria',
        'marketing', 'publicidade', 'design', 'gráfic', 'impress', 'seguro', 'rh', 'relação',
        'imobili', 'corretor', 'coworking', 'escritório', 'financeir', 'banco', 'fórum',
        'empréstimo', 'consórcio', 'terceiriza', 'segurança', 'recrutamento', 'portaria',
        'cartório', 'despachante', 'agente', 'associa', 'remessa', 'administrat', 'escrituração',
        'prefeitura', 'pública', 'público', 'correios', 'correio', 'tabelião', 'notaria', 'faixa', 'placa',
        'editora', 'fotó', 'foto', 'gravação', 'import', 'export', 'sindicato', 'ong', 'governo',
        'auditoria', 'investimento', 'pesquisa', 'bpo', 'call center', 'crédito', 'previdência', 
        'rastreamento', 'fundação', 'organiza', 'mídia', 'informação', 'radio', 'rádio', 'tv', 'jornal',
        'notícias', 'b2b', 'empresa', 'cooperativa', 'gestora', 'funeral', 'funerária', 'tradução',
        'polícia', 'delegacia', 'justiça', 'tribunal', 'alfândega', 'holding', 'mapeamento', 'carreira',
        'divórcio', 'mediação', 'fiscal', 'social', 'desenvolvimento', 'religiosa', 'espírita', 
        'conselheiro', 'serigrafia', 'encadernador', 'service', 'serviços', 'comunidade', 'amparo',
        'vítimas', 'assembléia', 'comunitário', 'casa lar', 'assistência', 'televisão', 'pequenas causas',
        'crematório', 'inspeção', 'sanitária', 'previsão', 'tempo'
    ],
    "Educação & Ensino": [
        'escola', 'colégio', 'faculdade', 'universidade', 'curso', 'idiomas', 'aula',
        'inglês', 'ensino', 'educação', 'treinamento', 'creche', 'berçário', 'aprendizagem',
        'autoescola', 'música', 'dança', 'biblioteca', 'jardim de infância', 'educacional',
        'coaching', 'tutor', 'piano', 'violão', 'voz', 'estudos', 'curricular', 'politécnico',
        'preparação', 'estudantil', 'testes', 'instrutor'
    ],
    "Tecnologia & Informática": [
        'informática', 'computador', 'celular', 'smartphone', 'assistência técnica', 'telefonia',
        'software', 'ti ', 'tecnologia', 'internet', 'telecom', 'eletrônic', 'game', 'antena',
        'lan house', 'cyber', 'web', 'hospedagem', 'satélite', 'circuito', 'dados', 'recuperação',
        'armários inteligentes', 'drones', 'wi-fi'
    ],
    "Turismo & Lazer": [
        'hotel', 'pousada', 'hostel', 'hospedaria', 'viagem', 'turismo', 'evento', 'festa',
        'casamento', 'formatura', 'produtora', 'show', 'teatro', 'cinema', 'noturna',
        'museu', 'parque', 'camping', 'acampamento', 'recreação', 'motel', 'atração', 'pesca',
        'rancho', 'churrasco', 'galeria', 'arte', 'ateliê', 'cultural', 'pensão', 'turista',
        'artista', 'produtor musical', 'gravadora', 'karaokê', 'fliperama', 'animação', 'chalé',
        'praia', 'trilha', 'teleférico', 'entretenimento', 'retiro', 'vila', 'convenções',
        'estúdio', 'dj', 'club', 'aquário', 'casa de campo', 'férias', 'festival', 'animador',
        'balões', 'rock', 'lago', 'histórico', 'exibição', 'lapidário', 'numerólogo', 'life coach',
        'tobogã', 'sala vip', 'panorâmico', 'lodge', 'visitantes', 'central', 'conferências',
        'off-road', 'off road', 'escultura'
    ],
    "Indústria & Transformação": [
        'indústria', 'industrial', 'fábrica', 'fabricante', 'confecção', 'metalúrgica', 'siderúrgica', 
        'distribui', 'atacado', 'atacadista', 'fornecedor', 'máquina', 'equipamento', 'usina', 
        'abatedouro', 'fundição', 'produção', 'embalagem', 'embalagen', 'plástico', 'aço', 'ferro', 
        'alumínio', 'armazém', 'depósito', 'químic', 'tijolo', 'iluminação', 'cerâmica', 'vidro', 
        'tornearia', 'solda', 'mineração', 'reciclagem', 'descarte', 'tratamento', 'serraria', 
        'refinaria', 'destilaria', 'jateamento', 'corte', 'laser', 'estampagem', 'concreteira',
        'moinho', 'ferramenteiro', 'sucata', 'metal', 'montadora', 'pedreira', 'represa',
        'polimento', 'finalista', 'descartados', 'embalador'
    ],
    "Agro, Animais & Natureza": [
        'agro', 'agrícola', 'fazenda', 'sítio', 'pecuária', 'rural', 'viveiro', 'planta',
        'criação', 'criador', 'apiário', 'orquidário', 'canil', 'peixes', 'pesca', 'jardim',
        'selaria', 'rancho', 'avícola', 'florestal', 'gado', 'curtume', 'cavalo', 'pássaro',
        'abelha', 'aquicultura', 'agricultura', 'pomar', 'árvores', 'feira', 'babá', 'treinador',
        'ferrador', 'controle', 'vinhedo', 'granja', 'reserva', 'animais'
    ]
}

REGEX_PATTERNS = {}
for categoria, keywords in CATEGORIAS_KEYWORDS.items():
    pattern_str = '|'.join(map(re.escape, keywords))
    REGEX_PATTERNS[categoria] = re.compile(pattern_str, re.IGNORECASE)

# --- FUNÇÕES AUXILIARES ---

def normalizar_categoria(cat_google):
    if not cat_google or str(cat_google).strip() == "" or str(cat_google).lower() == "não identificada":
        return "Não Identificada / Outros"
    cat_str = str(cat_google).replace('-', ' ').replace('/', ' ')
    for categoria, pattern in REGEX_PATTERNS.items():
        if pattern.search(cat_str):
            return categoria
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

# Função para gerar link do WhatsApp (GLOBAL para uso em Excel e Preview)
def gerar_link_wa(row):
    if row['tipo_contato'] == "Celular":
        nums = "".join(filter(str.isdigit, str(row['telefone'])))
        if not nums.startswith("55"): nums = f"55{nums}"
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

# CACHE DE 24 HORAS
@st.cache_data(ttl=86400)
def get_all_data():
    all_rows = []
    step = 1000
    start = 0
    while True:
        # Traz apenas colunas essenciais do Supabase
        colunas_necessarias = "nome, telefone, site, categoria_google, nota, avaliacoes, endereco_completo, bairro, cidade, estado, data_extracao"

        res = supabase.table("leads").select(colunas_necessarias).range(start, start + step - 1).execute()
        rows = res.data
        all_rows.extend(rows)
        if len(rows) < step: break
        start += step
        
    df = pd.DataFrame(all_rows)
    if not df.empty:
        # ==============================================================
        # 🚀 OTIMIZAÇÃO CRÍTICA DE MEMÓRIA (LINHAS 260-270)
        # ==============================================================
        # Converte colunas repetitivas para 'category' economizando até 80% de RAM
        cols_otimizaveis = ['estado', 'cidade', 'bairro', 'categoria_google']
        for col in cols_otimizaveis:
            if col in df.columns:
                df[col] = df[col].astype('category')

        # Reduz uso de memória em números
        if 'nota' in df.columns:
            # Troca virgula por ponto E converte para float32 (mais leve)
            df['nota'] = pd.to_numeric(df['nota'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0).astype('float32')
        
        if 'avaliacoes' in df.columns:
            # Converte para int32 (mais leve que int64)
            df['avaliacoes'] = pd.to_numeric(df['avaliacoes'].astype(str).str.replace('.', '', regex=False), errors='coerce').fillna(0).astype('int32')
        else:
            df['avaliacoes'] = 0
            
        # Tratamento de strings restantes
        # Note: bairro e estado já foram convertidos para category acima, então não precisamos preencher NA aqui de novo se já estiverem limpos, 
        # mas caso tenha NAs na origem, o 'astype category' lida bem.
        # Ajustamos o preenchimento ANTES de converter se necessário, mas aqui mantemos o fluxo simples.
        if 'bairro' in df.columns and df['bairro'].dtype.name != 'category':
             df['bairro'] = df['bairro'].fillna('Não informado')
             
        if 'estado' in df.columns and df['estado'].dtype.name != 'category':
             df['estado'] = df['estado'].fillna('N/A')
             
        if 'categoria_google' not in df.columns: 
             df['categoria_google'] = 'Outros'
        
        # Preenche NAs em categorias adicionando a categoria primeiro se necessário
        # (Simplificação: Pandas moderno lida bem com NAs em category, ou podemos ignorar por hora)

        # Segmento também deve ser Categoria
        df['Segmento'] = df['categoria_google'].apply(normalizar_categoria).astype('category')
        
        # Tipo contato também deve ser Categoria
        df['tipo_contato'] = df['telefone'].apply(classificar_telefone_global).astype('category')
        
        if 'data_extracao' in df.columns:
            df['data_obj'] = pd.to_datetime(df['data_extracao'], errors='coerce')
            df['data_fmt'] = df['data_obj'].dt.strftime('%d/%m/%Y').fillna(datetime.today().strftime('%d/%m/%Y'))
        else:
            df['data_fmt'] = datetime.today().strftime('%d/%m/%Y')
        
        def limpar_url_site(url):
            if not url: return None
            url_str = str(url).strip()
            if "business.google.com" in url_str: return None
            if "google.com/view" in url_str: return None 
            return url_str

        df['site'] = df['site'].apply(limpar_url_site)
        
        # Filtragem final
        df = df[df['tipo_contato'].isin(['Celular', 'Fixo'])]
        
    return df

# ==========================================
# 🚀 LÓGICA DE FLUXO E PAGAMENTO
# ==========================================

# 1. Verifica Estado do Pagamento ANTES de carregar filtros
if 'ref_venda' not in st.session_state:
    st.session_state.ref_venda = f"REF_{int(time.time())}"

check_banco = supabase.table("vendas").select("*").eq("external_reference", st.session_state.ref_venda).execute()
is_pago = check_banco.data and check_banco.data[0]['status'] == 'pago'

st.title(f"🚀 {NOME_MARCA}")

# -----------------------------------------------------------------
# CENÁRIO A: JÁ PAGO (TELA DE DOWNLOAD LIMPA)
# -----------------------------------------------------------------
if is_pago:
    st.balloons()
    
    st.success("✅ **PAGAMENTO CONFIRMADO!**")
    st.markdown("""
    <div class="warning-box">
    ⚠️ ATENÇÃO: BAIXE SEU ARQUIVO AGORA!<br>
    Ou verifique se você recebeu o link no seu e-mail.<br>
    Se fechar esta página sem baixar, chame o suporte no WhatsApp.
    </div>
    """, unsafe_allow_html=True)
    
    # Busca o arquivo direto do Storage
    nome_arquivo = f"{st.session_state.ref_venda}.xlsx"
    try:
        arquivo_bin = supabase.storage.from_('leads_pedidos').download(nome_arquivo)
        
        c_down1, c_down2 = st.columns([2, 1])
        with c_down1:
            st.download_button(
                label="📥 BAIXAR MINHA PLANILHA AGORA",
                data=arquivo_bin,
                file_name=f"leads_{st.session_state.ref_venda}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
        with c_down2:
            if st.button("🔄 Fazer Nova Busca", use_container_width=True):
                st.session_state.clear()
                st.rerun()
                
    except Exception as e:
        st.error("Erro ao recuperar arquivo. Por favor, contate o suporte.")
        st.info(f"Ref Venda: {st.session_state.ref_venda}")

# -----------------------------------------------------------------
# CENÁRIO B: NÃO PAGO (MOSTRA FILTROS E CHECKOUT)
# -----------------------------------------------------------------
else:
    st.markdown("### A plataforma de inteligência de dados locais.")
    st.caption("Enriqueça seu CRM com dados públicos, atualizados e validados do Google Maps.")

    # --- MELHORIA 1: Guia Rápido ---
    st.info("💡 **Como usar:** 1. Filtre pelo seu Nicho e Cidade > 2. Baixe uma amostra grátis > 3. Garanta a lista completa.")

    # --- TABELA DE PREÇOS ---
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
            st.markdown("#### 📉 Descontos Progressivos")
            st.info("Comece pequeno, escale pagando centavos.")
            st.markdown("""
            | Faixa (Leads Adicionais) | Preço Unitário |
            | :--- | :--- |
            | Primeiros 300 | **R$ 0,25** |
            | 301 a 1.000 | **R$ 0,15** |
            | 1.001 a 3.000 | **R$ 0,10** |
            | 3.001 a 5.000 | **R$ 0,06** |
            | + 5.000 | **R$ 0,04** |
            """)

    st.divider()

    # Só carrega os dados SE NÃO ESTIVER PAGO (Economiza recurso)
    with st.spinner("🔄 Conectando ao servidor seguro e baixando dados... Aguarde um instante."):
        df_raw = get_all_data()

    # --- FILTROS ---
    with st.container(border=True):
        st.subheader("🛠️ Configure sua Lista")
        c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 1, 1])
        
        # --- MELHORIA 2: Placeholders ---
        with c1: busca_nome = st.text_input("Buscar Nome", placeholder="Ex: Padaria do João, Oficina...")
        with c2: nota_range = st.select_slider("Nota Mínima", options=[i/10 for i in range(0, 51)], value=(0.0, 5.0))
        with c3: avaliacoes_range = st.slider("Qtd. Avaliações", 0, 5000, (0, 5000), step=10, help="Filtre pela popularidade.")
        with c4: filtro_site = st.radio("Site?", ["Todos", "Sim", "Não"], horizontal=True)
        with c5: filtro_tel = st.radio("Telefone", ["Todos (Móvel/Fixo)", "Apenas Celular", "Apenas Fixo"], horizontal=True, index=0)

        t1, t2 = st.tabs(["🎯 Segmentação", "📍 Localização"])

        with t1:
            col_a, col_b = st.columns(2)
            with col_a:
                # Otimização: unique em categorias é ultra rápido
                opts_macro = sorted(df_raw['Segmento'].unique().tolist()) if not df_raw.empty else []
                f_macro = st.multiselect("Setor Principal", opts_macro, placeholder="Selecione um ou mais setores...")
            with col_b:
                if f_macro: df_nicho_opts = df_raw[df_raw['Segmento'].isin(f_macro)]
                else: df_nicho_opts = df_raw
                # Convertemos para list para garantir compatibilidade com multiselect
                opts_nicho = sorted(df_nicho_opts['categoria_google'].unique().astype(str).tolist()) if not df_nicho_opts.empty else []
                f_google = st.multiselect("Nicho Específico", opts_nicho, placeholder="Ex: Dentistas, Pet Shops...")

        with t2:
            col_d, col_e, col_f = st.columns(3)
            opts_uf = sorted(df_raw['estado'].unique().astype(str).tolist()) if not df_raw.empty else []
            with col_d: f_uf = st.multiselect("Estado (UF)", opts_uf, placeholder="Selecione a UF...")
            
            if f_uf: df_cid_opts = df_raw[df_raw['estado'].isin(f_uf)]
            else: df_cid_opts = df_raw
            opts_cidade = sorted(df_cid_opts['cidade'].unique().astype(str).tolist()) if not df_cid_opts.empty else []
            with col_e: f_cidade = st.multiselect("Cidade", opts_cidade, placeholder="Ex: Campinas, São Paulo...")
            
            if f_cidade: df_bai_opts = df_cid_opts[df_cid_opts['cidade'].isin(f_cidade)]
            else: df_bai_opts = df_cid_opts
            opts_bairro = sorted(df_bai_opts['bairro'].unique().astype(str).tolist()) if not df_bai_opts.empty else []
            with col_f: f_bairro = st.multiselect("Bairro", opts_bairro, placeholder="Selecione o Bairro...")

    # --- APLICAÇÃO DOS FILTROS ---
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
        with m1: st.metric("Empresas Válidas", f"{len(df_raw):,}".replace(",", "."))
        with m2: st.metric("Cidades", f"{df_raw['cidade'].nunique()}")
        with m3: st.metric("Setores", f"{df_raw['Segmento'].nunique()}")
        st.markdown("---")

    else:
        total_leads = len(df_f)
        resumo_preco = calcular_preco_final(total_leads)
        valor_total = round(resumo_preco['total'], 2)

        st.divider()

        # --- MELHORIA 3: Tratamento de Zero Resultados ---
        if total_leads == 0:
            st.markdown("""
            <div class="warning-box">
            ⚠️ Ainda não temos leads com esses critérios exatos.
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("### 📢 Mas nós conseguimos ela para você!")
            st.write("Nossa equipe pode fazer uma varredura personalizada agora. Como você nos ajuda a mapear, ganha **25% de DESCONTO**.")
            
            msg_encomenda = "Olá, tentei buscar uma lista no site e não encontrei resultados. Gostaria de encomendar uma varredura personalizada com 25% de desconto."
            st.link_button(
                "💎 Encomendar Varredura com 25% OFF", 
                f"https://wa.me/5511963048466?text={msg_encomenda.replace(' ', '%20')}",
                type="primary"
            )

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
                    
                    # Barra de progresso visual
                    faixas_limites = [0, 300, 1000, 3000, 5000]
                    limite_anterior = 0
                    for L in faixas_limites:
                        if total_leads >= L: limite_anterior = L
                        else: break
                    
                    denominador = meta - limite_anterior
                    numerador = total_leads - limite_anterior
                    # Evitar divisão por zero e travar em 95% visualmente
                    if denominador > 0:
                        progresso = min(numerador / denominador, 0.95)
                    else:
                        progresso = 0
                        
                    st.write("")
                    st.progress(progresso)
                    st.caption(f"💡 Falta pouco: Adicione mais **{faltam} leads** para pagar só **{fmt_real(preco_futuro)}** nos próximos!")
                else:
                      st.success(f"💎 **Nível Atacado:** Você desbloqueou o menor preço do mercado ({fmt_real(0.04)}/lead nos adicionais)!")

            # --- MELHORIA 4: Banner de Oportunidade (Dark Mode Ready) ---
            st.warning("🕵️ **Não encontrou tudo o que queria?** Nossa base cresce todo dia. Encomende o que falta e ganhe **25% de DESCONTO**.")
            
            msg_banner = "Olá, encontrei alguns leads no site, mas queria encomendar uma lista maior/específica com o desconto de 25%."
            st.link_button(
                "👉 Encomendar Varredura Personalizada", 
                f"https://wa.me/5511963048466?text={msg_banner.replace(' ', '%20')}",
                type="primary",
                use_container_width=True
            )
            
            st.write("") # Espaço

            with st.container(border=True):
                st.subheader("📬 Finalizar Compra")
                ce1, ce2 = st.columns(2)
                
                # --- AJUSTE UX: Texto de Ajuda no E-mail ---
                with ce1: email_input = st.text_input("Seu E-mail", placeholder="seu@email.com", help="Garante que você receba o arquivo mesmo se fechar a página.")
                with ce2: email_confirm = st.text_input("Confirme seu E-mail", placeholder="seu@email.com")
                
                if email_input and email_confirm and (email_input != email_confirm):
                    st.warning("⚠️ Os e-mails não coincidem.")
                
                pode_prosseguir = (email_input == email_confirm) and ("@" in email_input)

                if st.button("💳 IR PARA PAGAMENTO SEGURO", type="primary", use_container_width=True, disabled=not pode_prosseguir):
                    
                    # Prepara e sobe arquivo AGORA
                    df_final = pd.DataFrame()
                    df_final['Empresa'] = df_f['nome']
                    
                    # --- REORDENAÇÃO DAS COLUNAS AQUI (VERSÃO PAGA) ---
                    # 1. Tipo antes do número
                    df_final['Tipo de Telefone'] = df_f['tipo_contato']
                    
                    # 2. Número
                    df_final['Telefone'] = df_f['telefone']
                    
                    # 3. Link logo após o número
                    df_final['Link WhatsApp'] = df_f.apply(gerar_link_wa, axis=1)
                    
                    # 4. Restante das colunas originais
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

                    # Cria registro pendente
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

        # 3. Análise Visual (Só aparece se NÃO pago)
        st.divider()
        st.subheader("📋 Amostra dos Dados (Top 50)")
        
        # --- MELHORIA 5: Botão Amostra Grátis (Download Real e Igual ao Pago) ---
        if total_leads > 0:
            st.markdown(" Quer validar antes? Baixe os **5 primeiros leads** completos (sem máscara) agora.")
            
            # 1. Pega os dados brutos (Top 5)
            raw_amostra = df_f.head(5).copy()

            # 2. Cria o DF formatado igual ao pago (MESMA ESTRUTURA)
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
                worksheet.set_column('A:A', 30) # Empresa
                worksheet.set_column('D:D', 25) # Link WhatsApp
            
            st.download_button(
                label="🎁 BAIXAR AMOSTRA GRÁTIS (Top 5)",
                data=buffer_amostra.getvalue(),
                file_name="amostra_diskleads_top5.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Baixe 5 leads reais para testar a qualidade."
            )

        df_preview = pd.DataFrame()
        df_preview['Empresa'] = df_f['nome']
        # Mascaramos a visualização na tela para forçar o download ou compra
        df_preview['Telefone'] = df_f['telefone'].apply(lambda x: str(x)[:-4] + "****" if x and len(str(x)) > 4 else "****")
        
        # Mostra na tabela que o link existe, mas está bloqueado
        df_preview['Link WhatsApp'] = df_f['tipo_contato'].apply(lambda x: "🔒 No Excel" if x == "Celular" else "-")
        
        df_preview['Tipo'] = df_f['tipo_contato']
        df_preview['Setor'] = df_f['Segmento']
        df_preview['Nicho'] = df_f['categoria_google']
        df_preview['Cidade'] = df_f['cidade']
        df_preview['Nota'] = df_f['nota']
        df_preview['Avaliações'] = df_f['avaliacoes']
        df_preview['Atualizado em'] = df_f['data_fmt']
        
        st.dataframe(df_preview.head(50), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("📊 Raio-X da Base Selecionada")
        g1, g2, g3 = st.columns(3)
        with g1: st.bar_chart(df_f['cidade'].value_counts().head(10), color="#2E66F1", horizontal=True)
        with g2: st.bar_chart(df_f['bairro'].value_counts().head(10), color="#2ecc71", horizontal=True)
        with g3: st.bar_chart(df_f['Segmento'].value_counts(), color="#f39c12", horizontal=True)


# ==========================================
# 🛡️ RODAPÉ E SUPORTE
# ==========================================
st.divider()
col_f1, col_f2 = st.columns(2)

with col_f1:
    st.markdown("#### 📞 Precisa de Ajuda?")
    st.markdown("Teve problemas com o pagamento ou download? Fale com o suporte.")
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
    