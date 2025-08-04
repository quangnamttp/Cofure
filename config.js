const TelegramBot = require('node-telegram-bot-api');
const { TELEGRAM_BOT_TOKEN, TELEGRAM_USER_IDS } = require('./config');

const dayjs = require('dayjs');
require('dayjs/locale/vi');
const utc = require('dayjs/plugin/utc');
const timezone = require('dayjs/plugin/timezone');

dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.locale('vi');

const bot = new TelegramBot(TELEGRAM_BOT_TOKEN, { polling: true });
console.log('🤖 Cofure bot đã khởi động!');

global.bot = bot;
global.USER_IDS = TELEGRAM_USER_IDS;

require('./web');

// Gửi phản hồi khi người dùng nhấn /start
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  const timeVN = dayjs().tz('Asia/Ho_Chi_Minh').format('HH:mm:ss');
  bot.sendMessage(chatId, `✅ Xin chào! Cofure bot đã sẵn sàng hoạt động vào lúc ${timeVN}!`);
});
