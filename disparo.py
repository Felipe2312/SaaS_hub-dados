import time
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client
from dotenv import load_dotenv

# Carrega variáveis de ambiente (mesmo .env dos outros arquivos)
load_dotenv()

# --- CONFIGURAÇÕES ---
# IMPORTANTE: Aqui você PRECISA da 'SERVICE_ROLE_KEY' se tiver RLS ativado no banco.
# Se não tiver RLS (Row Level Security), a chave anon/public funciona.
# Mas recomendo usar a Service Role para o robô ter permissão de escrita garantida.
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") # Idealmente, use a SERVICE_ROLE aqui

# Configurações de E-mail
EMAIL_REMETENTE = "suporte.diskleads@gmail.com"
# Se não estiver no .env, coloque a senha direta aqui, mas cuidado ao compartilhar o código
SENHA_APP = os.getenv("EMAIL_PASSWORD") or "mkry hsfu hxna upqp" 

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Erro: Configure SUPABASE_URL e SUPABASE_KEY no arquivo .env")
    exit()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def enviar_email_venda(destinatario, link_arquivo, ref, resumo_pedido):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"DiskLeads <{EMAIL_REMETENTE}>"
        msg['To'] = destinatario
        msg['Subject'] = f"🚀 Seus Leads Chegaram! (Ref: {ref})"

        # Formata o resumo para ficar bonito no email
        if not resumo_pedido: resumo_pedido = "Base de dados completa"

        corpo = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px;">
                    <h2 style="color: #2e66f1;">Pagamento Confirmado!</h2>
                    <p>Olá! Seu pedido foi processado e sua lista já foi gerada com sucesso.</p>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 5px 0;"><strong>🆔 Referência:</strong> {ref}</p>
                        <p style="margin: 5px 0;"><strong>📂 Conteúdo:</strong> {resumo_pedido}</p>
                    </div>

                    <p>Clique no botão abaixo para baixar sua planilha Excel:</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{link_arquivo}" style="background-color: #2ecc71; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">📥 BAIXAR LEADS AGORA</a>
                    </div>
                    
                    <p style="font-size: 12px; color: #777;">Se o botão não funcionar, copie e cole este link: <br>{link_arquivo}</p>
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                    <p style="font-size: 14px;">Obrigado por escolher o <strong>DiskLeads</strong>.<br>Att, Equipe de Suporte.</p>
                </div>
            </body>
        </html>
        """
        msg.attach(MIMEText(corpo, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_REMETENTE, SENHA_APP)
            server.sendmail(EMAIL_REMETENTE, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")
        return False

print("🤖 Robô de Disparo de E-mails INICIADO...")

while True:
    try:
        # Busca vendas PAGAS e NÃO ENVIADAS
        # Seleciona também a coluna 'detalhes_filtro' que criamos
        res = supabase.table("vendas")\
            .select("id, email_cliente, url_arquivo, external_reference, detalhes_filtro")\
            .eq("status", "pago")\
            .eq("enviado", False)\
            .execute()

        vendas_pendentes = res.data

        if vendas_pendentes:
            print(f"🔎 Encontrei {len(vendas_pendentes)} vendas para processar.")

        for venda in vendas_pendentes:
            email = venda['email_cliente']
            ref = venda['external_reference']
            filtros = venda.get('detalhes_filtro', 'Lista de Leads')
            
            print(f"   📧 Enviando para: {email} | Conteúdo: {filtros}")
            
            sucesso = enviar_email_venda(
                destinatario=email, 
                link_arquivo=venda['url_arquivo'], 
                ref=ref,
                resumo_pedido=filtros # Passamos o filtro para o email
            )

            if sucesso:
                # Marca como enviado no banco
                supabase.table("vendas")\
                    .update({"enviado": True})\
                    .eq("id", venda['id']).execute()
                print(f"   ✅ E-mail enviado e banco atualizado!")
            else:
                print(f"   ⚠️ Falha no envio. Tentarei novamente no próximo ciclo.")

    except Exception as e:
        print(f"❌ Erro no loop do robô: {e}")

    # Verifica a cada 10 segundos
    time.sleep(10)