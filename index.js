// index.js

const TelegramBot = require('node-telegram-bot-api');
const { TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS, TIMEZONE } = require('./config');
const dayjs = require('dayjs');
require('dayjs/locale/vi');
dayjs.locale('vi');

const bot = new TelegramBot(TELEGRAM_BOT_TOKEN, { polling: true });
console.log('🤖 Cofure bot đã khởi động!');

// Gán bot và danh sách ID người dùng cho toàn cục
global.bot = bot;
global.USER_IDS = TELEGRAM_USER_IDS;

// Load Web Server (dùng để ping giữ bot sống)
require('./web');

// ⚡ Test phản hồi lệnh /start
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id.toString();

  if (TELEGRAM_USER_IDS.includes(userId)) {
    bot.sendMessage(chatId, `✅ Xin chào! Cofure bot đã sẵn sàng hoạt động vào lúc ${dayjs().format('HH:mm:ss')}!`);
  } else {
    bot.sendMessage(chatId, `🚫 Bạn không có quyền sử dụng bot này.`);
  }
});
