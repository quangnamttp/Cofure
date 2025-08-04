const axios = require('axios');
const { bot } = require('../web');
const { users } = require('../config.json');
const dayjs = require('dayjs');
require('dayjs/locale/vi');
dayjs.locale('vi');

const BINANCE_API = 'https://fapi.binance.com/fapi/v1/ticker/24hr';
const API_KEY = 'T0mr8sxbqOqQHDERygnXT44vN3tHVqfcJowfxpfHJOta6Bse4nnS61zeh71KIflM'; // ← key bạn đưa

function getVietnamTime() {
  return dayjs().tz('Asia/Ho_Chi_Minh').format('HH:mm:ss');
}

async function sendMorningReport() {
  try {
    const res = await axios.get(BINANCE_API, {
      headers: { 'X-MBX-APIKEY': API_KEY }
    });

    const allSymbols = res.data.filter(d => d.symbol.endsWith('USDT'));
    const sorted = allSymbols
      .filter(c => +c.priceChangePercent > 0)
      .sort((a, b) => +b.priceChangePercent - +a.priceChangePercent)
      .slice(0, 5);

    const messageLines = sorted.map((coin, index) => {
      const trend = +coin.priceChangePercent > 10 ? '📈 Mạnh' : +coin.priceChangePercent > 5 ? '📊 Tăng nhẹ' : '↗️ Nhẹ';
      return `#${index + 1} • ${coin.symbol.replace('USDT', '')}
🔺 Tăng: +${(+coin.priceChangePercent).toFixed(2)}%
💸 Volume: ${(coin.quoteVolume / 1e6).toFixed(1)}M USDT
📈 Xu hướng: ${trend}`;
    });

    const greeting = `☀️ Chào buổi sáng nhé! ${dayjs().format('dddd, DD/MM')}  
Dưới đây là 5 đồng coin nổi bật nhất 24h qua:\n\n${messageLines.join('\n\n')}
    
💡 Hãy theo dõi kỹ funding, volume và xu hướng thị trường hôm nay nha!
Chúc bạn một ngày giao dịch hiệu quả! 💪`;

    // Gửi đến từng user
    for (const u of users) {
      await bot.sendMessage(u.id, `Chào buổi sáng, ${u.name} 🌤️`);
      await bot.sendMessage(u.id, greeting);
    }

    console.log(`✅ Đã gửi bản tin sáng lúc ${getVietnamTime()}`);
  } catch (err) {
    console.error('❌ Lỗi gửi bản tin sáng:', err.message);
  }
}

module.exports = sendMorningReport;
