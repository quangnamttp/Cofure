const TelegramBot = require('node-telegram-bot-api');
const config = require('./config');

const bot = new TelegramBot(config.TELEGRAM_BOT_TOKEN, { polling: true });

// Log lỗi nếu có
bot.on('polling_error', console.log);

// Phản hồi khi người dùng nhắn /start
bot.onText(/\/start/, (msg) => {
  bot.sendMessage(msg.chat.id, `🤖 Bot Cofure đã sẵn sàng hoạt động!`);
});
