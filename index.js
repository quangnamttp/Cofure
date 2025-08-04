const TelegramBot = require('node-telegram-bot-api');
const { TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS, TIMEZONE } = require('./config');
const dayjs = require('dayjs');
const utc = require('dayjs/plugin/utc');
const timezone = require('dayjs/plugin/timezone');
require('dayjs/locale/vi');

// Cấu hình múi giờ
dayjs.locale('vi');
dayjs.extend(utc);
dayjs.extend(timezone);

// Tạo bot không dùng polling
const bot = new TelegramBot(TELEGRAM_BOT_TOKEN);
bot.setWebHook(`https://cofure.onrender.com/bot${TELEGRAM_BOT_TOKEN}`);
console.log('🤖 Cofure bot đã khởi động với Webhook!');

// Gán bot và danh sách ID người dùng cho toàn cục
global.bot = bot;
global.USER_IDS = TELEGRAM_USER_IDS;

// Load Web Server để Telegram gửi webhook về
require('./web');

// Xử lý lệnh /start
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id.toString();

  const timeVN = dayjs().tz(TIMEZONE).format('HH:mm:ss');

  if (TELEGRAM_USER_IDS.includes(userId)) {
    bot.sendMessage(chatId, `✅ Xin chào! Cofure bot đã sẵn sàng hoạt động vào lúc ${timeVN}!`);
  } else {
    bot.sendMessage(chatId, `🚫 Bạn không có quyền sử dụng bot này.`);
  }
});
