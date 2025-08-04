const express = require('express');
const bodyParser = require('body-parser');
const { TELEGRAM_BOT_TOKEN } = require('./config');

const app = express();
app.use(bodyParser.json());

// Endpoint để Telegram gửi update về
app.post(`/bot${TELEGRAM_BOT_TOKEN}`, (req, res) => {
  if (global.bot) {
    global.bot.processUpdate(req.body);
  }
  res.sendStatus(200);
});

// Ping URL để giữ bot sống
app.get('/', (req, res) => {
  res.send('🤖 Cofure bot đang hoạt động với Webhook!');
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log(`🌐 Web server đang chạy trên port ${PORT}`);
});
