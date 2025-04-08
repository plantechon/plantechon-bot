
from flask import Flask, request, jsonify
import requests
import threading
import time
import datetime
import random
import os
from pytz import timezone

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TIMEZONE = timezone("America/Sao_Paulo")
SIGNAL_COOLDOWN = 300
INACTIVITY_CHECK = 3600

TEMPLATE_MENSAGEM = """📢 *{titulo}*
🔹 *Ativo*: `{pair}`
🔹 *Tempo Gráfico*: {timeframe}
🔹 *Preço de Entrada*: `{price:.2f}`
🎯 *Alvos Técnicos*:
├ 🎯 1º Alvo: `{tp1:.2f}` ({gain1:+.1f}%)
├ 🎯 2º Alvo: `{tp2:.2f}` ({gain2:+.1f}%)
└ 🎯 3º Alvo: `{tp3:.2f}` ({gain3:+.1f}%)
🛡 *Gestão de Risco*:
├ ⛔ *Stop Loss*: `{sl:.2f}` ({sl_percent:+.1f}%)
└ ✅ *Alvo Principal (TP)*: `{tp3:.2f}` ({gain3:+.1f}%)
📊 *Parâmetros Técnicos*:
├ 📈 Volatilidade (ATR): `{atr:.2f}`
├ 📈 Risco x Retorno (TP3): {rr:.1f} : 1
├ 📈 Média Risco x Retorno: {rr_media:.1f} : 1
└ ⚙️ Alavancagem Recomendada: {leverage}x
📘 *Setup Estratégico*: Plantechon Pro v2  
⏱ *Horário do Sinal*: {timestamp}
"""

MENSAGENS_INATIVIDADE = [
    "📊 Sem sinais no momento.",
    "⚖️ Aguardando confirmação técnica.",
    "📉 Nenhuma entrada validada agora.",
    "🔍 Análise em andamento.",
    "🧠 Mercado sem confluência.",
    "⏳ Setup ainda não alinhado.",
    "🚫 Nenhuma oportunidade ativa.",
    "🕵️‍♂️ Monitorando o cenário.",
    "📵 Sem volume ou estrutura ideal.",
    "📋 Critérios técnicos não atendidos."
]

app = Flask(__name__)
last_signal = {'time': None, 'pair': None, 'action': None}

def send_telegram_alert(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print("📤 Mensagem enviada com sucesso para o Telegram.")
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar mensagem: {e}")
        return False

def verificar_inatividade():
    while True:
        time.sleep(INACTIVITY_CHECK)
        if not last_signal["time"] or (datetime.datetime.now() - last_signal["time"]).seconds >= INACTIVITY_CHECK:
            msg = random.choice(MENSAGENS_INATIVIDADE)
            send_telegram_alert(msg)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        print("✅ Sinal recebido na função webhook!")

        data = request.get_json()
        for campo in ["tipo", "ativo", "entrada", "risco_percent", "tp1_percent", "tp2_percent", "tp3_percent"]:
            if campo not in data:
                return jsonify({"erro": f"Falta o campo {campo}"}), 400

        tipo = data["tipo"].lower()
        ativo = data["ativo"]
        price = float(data["entrada"])
        risco_pct = float(data["risco_percent"])
        tp1_pct = float(data["tp1_percent"])
        tp2_pct = float(data["tp2_percent"])
        tp3_pct = float(data["tp3_percent"])
        atr = float(data.get("atr", 0))
        timeframe = data.get("timeframe", "N/D")
        timestamp = datetime.datetime.now(TIMEZONE).strftime("%d/%m %H:%M")
        now = datetime.datetime.now()

        if (last_signal["pair"] == ativo and last_signal["action"] == tipo and
            last_signal["time"] and (now - last_signal["time"]).seconds < SIGNAL_COOLDOWN):
            print(f"⏱ Cooldown ativo para {ativo} [{tipo.upper()}]")
            return jsonify({"status": "cooldown"}), 200

        risco = price * risco_pct / 100
        ret1 = price * tp1_pct / 100
        ret2 = price * tp2_pct / 100
        ret3 = price * tp3_pct / 100

        if tipo == "buy":
            sl = price - risco
            tp1 = price + ret1
            tp2 = price + ret2
            tp3 = price + ret3
            titulo = "🟢 SINAL DE COMPRA"
        else:
            sl = price + risco
            tp1 = price - ret1
            tp2 = price - ret2
            tp3 = price - ret3
            titulo = "🔴 SINAL DE VENDA"

        rr1 = abs((tp1 - price) / (price - sl))
        rr2 = abs((tp2 - price) / (price - sl))
        rr3 = abs((tp3 - price) / (price - sl))
        rr_media = round((rr1 + rr2 + rr3) / 3, 1)

        msg = TEMPLATE_MENSAGEM.format(
            titulo=titulo, pair=ativo, timeframe=timeframe, price=price,
            tp1=tp1, tp2=tp2, tp3=tp3,
            gain1=(tp1 - price) / price * 100,
            gain2=(tp2 - price) / price * 100,
            gain3=(tp3 - price) / price * 100,
            sl=sl, sl_percent=(sl - price) / price * 100,
            atr=atr, rr=round(rr3, 1), rr_media=rr_media,
            leverage=random.randint(3, 10),
            timestamp=timestamp
        )

        print("Mensagem formatada:")
        print(msg)

        if send_telegram_alert(msg):
            last_signal["time"] = now
            last_signal["pair"] = ativo
            last_signal["action"] = tipo

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    threading.Thread(target=verificar_inatividade, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
