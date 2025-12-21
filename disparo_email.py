import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

# --- CONFIGURAÇÕES ---
SUPABASE_URL = "https://wsqebbwjmiwiscbkmawy.supabase.co"
SUPABASE_KEY = "sb_publishable_FJ5VPfb8xD197JkISbCNOQ_hoGNC6U9" # Use a Service Role para o robô ter poder total
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

EMAIL_REMNETENTE = "suporte.diskleads@gmail.com"
SENHA_APP = "mkry hsfu hxna upqp" # Aquela de 16 dígitos

def enviar_email_venda(destinatario, link_arquivo, ref):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"DiskLeads <{EMAIL_REMNETENTE}>"
        msg['To'] = destinatario
        msg['Subject'] = f"🚀 Seus Leads Chegaram! (Ref: {ref})"

        corpo = f"""
        <html>
            <body>
                <h2>Pagamento Confirmado!</h2>
                <p>Olá! Seu pedido foi processado com sucesso.</p>
                <p><strong>Referência:</strong> {ref}</p>
                <p>Clique no botão abaixo para baixar sua lista de leads em Excel:</p>
                <a href="{link_arquivo}" style="background-color: #2ecc71; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">BAIXAR LEADS AGORA</a>
                <br><br>
                <p>Obrigado por escolher o DiskLeads!</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(corpo, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_REMNETENTE, SENHA_APP)
            server.sendmail(EMAIL_REMNETENTE, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"Erro ao enviar email: {e}")
        return False

print("🤖 Robô DiskLeads iniciado e monitorando vendas...")

while True:
    try:
        # Busca vendas que estão PAGAS mas ainda NÃO FORAM ENVIADAS
        res = supabase.table("vendas")\
            .select("*")\
            .eq("status", "pago")\
            .eq("enviado", False).execute()

        vendas_pendentes = res.data

        for venda in vendas_pendentes:
            print(f"📧 Enviando e-mail para: {venda['email_cliente']} (Ref: {venda['external_reference']})")
            
            sucesso = enviar_email_venda(
                venda['email_cliente'], 
                venda['url_arquivo'], 
                venda['external_reference']
            )

            if sucesso:
                # Marca como enviado para não mandar duas vezes
                supabase.table("vendas")\
                    .update({"enviado": True})\
                    .eq("id", venda['id']).execute()
                print(f"✅ Sucesso!")

    except Exception as e:
        print(f"Erro no loop do robô: {e}")

    time.sleep(15) # Checa a cada 15 segundos