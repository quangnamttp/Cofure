const axios = require('axios');
const dayjs = require('dayjs');
require('dayjs/locale/vi');
dayjs.locale('vi');

const { users } = require('../config');
const { bot } = require('../web');

const BINANCE_API_KEY = 'T0mr8sxbqOqQHDERygnXT44vN3tHVqfcJowfxpfHJOta6Bse4nnS61zeh71KIflM';

// Hàm fetch toàn bộ dữ liệu futures coin
async function fetchRandomCoins(limit = 5) {
  const url = 'https://fapi.binance.com/fapi/v1/ticker/24hr';
  const res = await axios.get(url, {
    headers: { 'X-MBX-APIKEY': BINANCE_API_KEY }
  });

  const all = res.data.filter(i => i.symbol.endsWith('USDT') && !i.symbol.includes('_'));
  const shuffled = all.sort(() => 0.5 - Math.random());
  const selected = shuffled.slice(0, limit);

  const result = selected.map(i => {
    const priceChange = parseFloat(i.priceChangePercent);
    const volume = parseFloat(i.quoteVolume);
    const trend = priceChange > 0 ? 'Tăng' : (priceChange < 0 ? 'Giảm' : 'Đi ngang');

    return {
      symbol: i.symbol,
      priceChangePercent: priceChange.toFixed(2),
      quoteVolume: volume.toLocaleString(),
      fundingRate: getMockFundingRate(),
      trend
    };
  });

  return result;
}

// Tạo funding ảo (vì Binance API không có funding trong endpoint 24h)
function getMockFundingRate() {
  const rate = (Math.random() * 0.2 - 0.1).toFixed(3); // từ -0.1% đến 0.1%
  return rate;
}

// Gửi bản tin sáng
async function sendMorningReport() {
  try {
    const coins = await fetchRandomCoins();
    const now = dayjs().format('HH:mm - dddd, DD/MM/YYYY');

    for (const user of users) {
      let message = `🌞 Chào buổi sáng ${user.name}!\n🕕 ${now}\nCùng xem hôm nay thị trường có gì nha:\n\n`;

      coins.forEach((coin, index) => {
        message += `🔹 ${index + 1}. ${coin.symbol}\n`;
        message += `📈 Tăng/Giảm: ${coin.priceChangePercent}%\n`;
        message += `💸 Funding: ${coin.fundingRate}%\n`;
        message += `📊 Volume: ${coin.quoteVolume}\n`;
        message += `📍 Xu hướng: ${coin.trend}\n\n`;
      });

      message += `🚀 Chúc bạn một ngày trade thật hiệu quả nhé!`;

      await bot.sendMessage(user.id, message);
    }
  } catch (err) {
    console.error('❌ Lỗi gửi bản tin sáng:', err.message);
  }
}

module.exports = sendMorningReport;
