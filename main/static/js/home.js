window.onload = function() {
    fetch('https://api.coingecko.com/api/v3/global')
        .then(response => response.json())
        .then(data => {
            const marketData = data.data;

            // 更新總市值和24小時交易量
            document.getElementById('total_market_cap').textContent = marketData.total_market_cap.usd.toLocaleString();
            document.getElementById('total_24h_volume').textContent = marketData.total_volume.usd.toLocaleString();

            // 取得比特幣、以太坊和其他幣種的市占率
            const btcDominance = marketData.market_cap_percentage.btc.toFixed(2);
            const ethDominance = marketData.market_cap_percentage.eth.toFixed(2);
            const otherDominance = (100 - btcDominance - ethDominance).toFixed(2);

            // 更新市占率顯示
            document.getElementById('btc_dominance').textContent = `比特幣: ${btcDominance}%`;
            document.getElementById('eth_dominance').textContent = `以太坊: ${ethDominance}%`;
            document.getElementById('other_dominance').textContent = `其他: ${otherDominance}%`;
        })
        .catch(error => {
            console.error('無法取得市場數據:', error);
            document.getElementById('total_market_cap').textContent = '無法取得';
            document.getElementById('total_24h_volume').textContent = '無法取得';
            document.getElementById('btc_dominance').textContent = '無法取得';
            document.getElementById('eth_dominance').textContent = '無法取得';
            document.getElementById('other_dominance').textContent = '無法取得';
        });
}

const backToTopButton = document.getElementById("backToTop");

// 監聽滾動事件
window.onscroll = function() {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop;
    if (scrollTop > 100) { 
        backToTopButton.style.display = "block"; // 滾動超過 100px 顯示按鈕
    } else {
        backToTopButton.style.display = "none"; // 否則隱藏按鈕
    }
};

// 點擊按鈕回到頂部
backToTopButton.onclick = function() {
    window.scrollTo({
        top: 0,
        behavior: "smooth" // 平滑滾動效果
    });
};

function showContent(id) {
    // 隱藏所有內容區塊
    var contents = document.querySelectorAll('.card-coin');
    contents.forEach(function(content) {
        content.classList.remove('active');
        console.log("123");
    });

    // 顯示選中的內容區塊
    var selectedContent = document.getElementById(id);
    selectedContent.classList.add('active');
}

document.addEventListener("DOMContentLoaded", function () {
    const cards = document.querySelectorAll(".card_invent");

    cards.forEach(card => {
        card.addEventListener("click", function () {
            // 先把所有已經翻轉的卡片恢復
            cards.forEach(c => {
                if (c !== card) {
                    c.classList.remove("active");
                }
            });

            // 切換當前卡片的翻轉狀態
            card.classList.toggle("active");
        });
    });
});

// 監視 `.carousel` 是否進入視口
const carousel = document.querySelector('.carousel');
const ball = document.getElementById('ball');
const path = document.getElementById('motionPath');
let isInView = false;

// 當 `.carousel` 進入視口時啟動滾動事件
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            isInView = true;  // `.carousel` 進入視口，開始處理滾動
            // 計算初始位置，避免瞬移
            updateBallPosition();
        } else {
            isInView = false; // `.carousel` 離開視口，停止滾動
        }
    });
}, { threshold: 0.5 });  // 設定當元素至少一半進入視口時觸發

observer.observe(carousel);

// 計算球的位置，並設置初始位置
const updateBallPosition = () => {
    const scrollY = window.scrollY;
    const pathLength = path.getTotalLength();
    let scrollPercent = scrollY / (document.body.scrollHeight - window.innerHeight);
    scrollPercent = Math.min(Math.max(scrollPercent, 0), 1);

    const point = path.getPointAtLength(scrollPercent * pathLength);
    ball.setAttribute('cx', point.x);
    ball.setAttribute('cy', point.y);
};

// 滾動事件處理
window.addEventListener('scroll', function() {
    if (!isInView) return;  // 如果 `.carousel` 沒有進入視口，則不執行下面的代碼

    // 更新球的位置
    updateBallPosition();
});

function animateBall(pathId, ballId, speed, callback) {
    const path = document.getElementById(pathId);
    const ball = document.getElementById(ballId);
    const pathLength = path.getTotalLength();

    let progress = 0;

    function moveBall() {
        progress += speed;
        if (progress > 1) {
            progress = 1;
        }

        const point = path.getPointAtLength(progress * pathLength);
        ball.setAttribute('cx', point.x);
        ball.setAttribute('cy', point.y);

        if (progress < 1) {
            requestAnimationFrame(moveBall);
        } else if (callback) {
            callback(); // 當動畫結束，執行 callback
        }
    }

    moveBall();
}

function startAnimationSequence() {
    animateBall("leftPath", "ballLeft", 0.005, () => {
        animateBall("rightPath", "ballRight", 0.005, () => {
            startAnimationSequence(); // 循環
        });
    });
}

startAnimationSequence(); // 啟動動畫