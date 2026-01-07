import os
import time
import pandas as pd
from supabase import create_client
from datetime import datetime
from dotenv import load_dotenv

# Carrega variáveis locais
load_dotenv()

# ==========================================
# ⚙️ CONFIGURAÇÕES
# ==========================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

DATA_DIR = "data"
CACHE_FILE = os.path.join(DATA_DIR, "leads.parquet")

# ==========================================
# 🔄 LOOP DE ATUALIZAÇÃO (MODO CURSOR ID)
# ==========================================
def main():
    print("🤖 Updater iniciado. Modo Turbo (Cursor ID).")
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Erro: SUPABASE_URL e SUPABASE_KEY são obrigatórios.")
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    while True:
        try:
            print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Baixando dados...")
            
            all_rows = []
            limit = 1000 # Lote seguro
            last_id = 0  # Começa do zero
            
            # Precisamos do ID para controlar o cursor
            cols = "id, nome, telefone, site, categoria_google, nicho, nota, avaliacoes, endereco_completo, bairro, cidade, estado, data_extracao, segmento, tipo_contato"

            while True:
                try:
                    # Lógica de Cursor: Pega os próximos 1000 APÓS o último ID visto
                    # Isso é infinitamente mais rápido que o .range()
                    res = supabase.table("leads")\
                        .select(cols)\
                        .gt("id", last_id)\
                        .order("id")\
                        .limit(limit)\
                        .execute()
                    
                    rows = res.data
                    
                    if not rows: break
                    
                    all_rows.extend(rows)
                    # Atualiza o cursor para o último ID desse lote
                    last_id = rows[-1]['id']
                    
                    if len(all_rows) % 5000 == 0:
                        print(f"   ... Baixados: {len(all_rows)} (Último ID: {last_id})")

                except Exception as e:
                    print(f"❌ Erro de conexão (ID > {last_id}): {e}")
                    time.sleep(5)
                    # Tenta de novo do mesmo ponto
                    continue

            print(f"⚡ Download concluído: {len(all_rows)} leads. Processando...")
            
            if len(all_rows) > 0:
                df = pd.DataFrame(all_rows)

                # --- LIMPEZA E OTIMIZAÇÃO ---
                
                # Garante números
                if 'nota' in df.columns:
                    df['nota'] = pd.to_numeric(df['nota'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0).astype('float32')
                if 'avaliacoes' in df.columns:
                    df['avaliacoes'] = pd.to_numeric(df['avaliacoes'], errors='coerce').fillna(0).astype('int32')

                # Preenche vazios visuais
                df['bairro'] = df['bairro'].fillna('Não informado')
                df['estado'] = df['estado'].fillna('BR')
                df['cidade'] = df['cidade'].fillna('Desconhecida')
                
                # Garante colunas essenciais
                if 'segmento' not in df.columns: df['segmento'] = 'Outros'
                if 'tipo_contato' not in df.columns: df['tipo_contato'] = 'Outro'

                # Formata data (apenas para display)
                if 'data_extracao' in df.columns:
                    df['data_obj'] = pd.to_datetime(df['data_extracao'], errors='coerce')
                    df['data_extracao'] = df['data_obj'] 

                # Descarta a coluna ID pois não precisamos dela no Excel/Dashboard, só serviu pro download
                if 'id' in df.columns:
                    df.drop(columns=['id'], inplace=True)

                # Categorização para reduzir tamanho do arquivo
                cols_cat = ['estado', 'cidade', 'bairro', 'categoria_google', 'segmento', 'tipo_contato', 'nicho']
                for col in cols_cat:
                    if col in df.columns:
                        df[col] = df[col].astype(str).astype('category')

                # Salvamento Seguro
                temp_file = os.path.join(DATA_DIR, "leads_temp.parquet")
                df.to_parquet(temp_file, compression='snappy')
                
                if os.path.exists(CACHE_FILE):
                    try: os.remove(CACHE_FILE)
                    except: pass
                
                os.rename(temp_file, CACHE_FILE)
                
                print(f"✅ SUCESSO! Base salva com {len(df)} empresas. Próxima atualização em 4h.")
            
            else:
                print("⚠️ Banco de dados vazio. Aguardando Scrapy rodar.")

        except Exception as e:
            print(f"❌ Erro fatal no Updater: {e}")

        # Atualiza a cada 4 horas
        time.sleep(14400) 

if __name__ == "__main__":
    main()
    