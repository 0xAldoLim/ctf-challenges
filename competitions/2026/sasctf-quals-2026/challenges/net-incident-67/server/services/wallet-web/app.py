import hashlib
import time

from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

WALLET_PAGE = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CryptoWallet - Secure Sasthereum Gateway</title>
    <style>
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box
      }

      body {
        background: #0a0e17;
        color: #c9d1d9;
        font-family: 'Segoe UI',system-ui,sans-serif;
        min-height: 100vh
      }

      .topbar {
        background: #161b22;
        border-bottom: 1px solid #30363d;
        padding: 14px 32px;
        display: flex;
        align-items: center;
        justify-content: space-between
      }

      .topbar .logo {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 20px;
        font-weight: 700;
        color: #58a6ff
      }

      .topbar .logo svg {
        width: 28px;
        height: 28px;
        fill: #58a6ff
      }

      .topbar .status {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
        color: #3fb950
      }

      .topbar .status::before {
        content: '';
        width: 8px;
        height: 8px;
        background: #3fb950;
        border-radius: 50%;
        display: inline-block
      }

      .container {
        max-width: 900px;
        margin: 0 auto;
        padding: 40px 20px
      }

      .hero {
        text-align: center;
        margin-bottom: 48px
      }

      .hero h1 {
        font-size: 28px;
        color: #f0f6fc;
        margin-bottom: 8px
      }

      .hero p {
        color: #8b949e;
        font-size: 15px
      }

      .cards {
        display: grid;
        grid-template-columns: repeat(auto-fit,minmax(260px,1fr));
        gap: 20px;
        margin-bottom: 40px
      }

      .card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 24px
      }

      .card h3 {
        color: #58a6ff;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 12px
      }

      .card .value {
        font-size: 32px;
        font-weight: 700;
        color: #f0f6fc
      }

      .card .sub {
        color: #8b949e;
        font-size: 13px;
        margin-top: 4px
      }

      .txform {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 32px
      }

      .txform h2 {
        color: #f0f6fc;
        font-size: 18px;
        margin-bottom: 20px
      }

      .field{
        margin-bottom: 16px
      }

      .field label{
        display: block;
        color: #8b949e;
        font-size: 13px;
        margin-bottom: 6px
      }

      .field input{
        width: 100%;
        padding: 10px 14px;
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 8px;
        color: #c9d1d9;
        font-size: 14px;
        outline: none
      }

      .field input: focus{
        border-color: #58a6ff
      }

      .btn{
        background: #238636;
        color: #fff;
        border: none;
        padding: 12px 24px;
        border-radius: 8px;
        font-size: 15px;
        cursor: pointer;
        font-weight: 600;
        width: 100%
      }
      
      .btn:hover{
        background: #2ea043
      }

      .footer{
        text-align: center;
        padding: 40px 20px;
        color: #484f58;
        font-size: 12px
      }

      .chain-badge{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #1c2128;
        border: 1px solid #30363d;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 12px;
        color: #8b949e
      }

      .chain-badge .dot{
        width: 6px;
        height: 6px;
        background: #a371f7;
        border-radius: 50%
      }

    </style>
  </head>
  <body>
    <div class="topbar">
      <div class="logo">
        <svg viewBox="0 0 24 24">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
        CryptoWallet
      </div>
      <div class="status">Connected — Mainnet</div>
    </div>
    <div class="container">
      <div class="hero">
        <h1>Secure Sasthereum Gateway</h1>
        <p>Enterprise-grade wallet infrastructure &middot; <span class="chain-badge"><span class="dot"></span>Sasthereum Mainnet</span></p>
      </div>
      <div class="cards">
        <div class="card">
          <h3>Network</h3>
          <div class="value">Sasthereum</div>
          <div class="sub">Chain ID: 1 &middot; Block: 21,847,293</div>
        </div>
        <div class="card">
          <h3>Gas Price</h3>
          <div class="value">12.4 Gwei</div>
          <div class="sub">Base fee &middot; ~$0.42 per transfer</div>
        </div>
        <div class="card">
          <h3>Status</h3>
          <div class="value" style="color:#3fb950">Operational</div>
          <div class="sub">All systems nominal</div>
        </div>
      </div>
      <div class="txform">
        <h2>Submit Transaction</h2>
        <div class="field">
          <label>Recipient Wallet Address</label>
          <input type="text" placeholder="0x..." id="wallet">
        </div>
        <div class="field">
          <label>Amount (ETH)</label>
          <input type="text" placeholder="0.0" id="amount">
        </div>
        <div class="field">
          <label>Memo</label>
          <input type="text" placeholder="Optional note" id="memo">
        </div>
        <button class="btn" onclick="submitTx()">Sign &amp; Send Transaction</button>
        <div id="result" style="margin-top:16px;font-size:13px;color:#8b949e"></div>
      </div>
    </div>
    <div class="footer">
      &copy; 2026 CryptoCloud Inc. &mdash; cryptowallet.ctf &mdash; All rights reserved.
    </div>
    <script>
      async function submitTx() {
        const r = document.getElementById('result');
        r.textContent = 'Signing transaction...';
        try {
          const res = await fetch('/api/v1/transaction', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({
              wallet:document.getElementById('wallet').value,
              amount:document.getElementById('amount').value,
              memo:document.getElementById('memo').value
            })
          });
          const d = await res.json();
          r.innerHTML = '<span style="color:#3fb950">✓ Confirmed</span> - TX: '+d.tx_id;
        }catch(e){
          r.innerHTML='<span style="color:#f85149">✗ Failed</span> - '+e.message;
        }
      }
    </script>
  </body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(WALLET_PAGE)


@app.route("/api/v1/status")
def status():
    return jsonify({"status": "online", "chain": "ethereum"})


@app.route("/api/v1/transaction", methods=["POST"])
def transaction():
    data = request.get_json(silent=True) or {}
    wallet = data.get("wallet", "")
    amount = data.get("amount", "0")
    memo = data.get("memo", "")

    tx_hash = hashlib.sha256(
        f"{wallet}{amount}{memo}{time.time()}".encode()
    ).hexdigest()

    tx_id = f"0x{tx_hash[:64]}"

    app.logger.info(
        "Transaction received: wallet=%s amount=%s memo=%s tx_id=%s",
        wallet,
        amount,
        memo[:32],
        tx_id,
    )

    return jsonify(
        {
            "tx_id": tx_id,
            "status": "confirmed",
            "block": 21847293,
            "gas_used": 21000,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=False)
