let currentSlideIndex = 0;
let sliderInterval = null;

// слайдер
function initSlider() {
    const slides = document.querySelectorAll('.slide');
    const dots = document.querySelectorAll('.dot');
    const totalSlides = slides.length;
    
    if (totalSlides === 0) return;
    
    if (sliderInterval) clearInterval(sliderInterval);
    sliderInterval = setInterval(() => {
        currentSlideIndex = (currentSlideIndex + 1) % totalSlides;
        showSlide(currentSlideIndex);
    }, 5000);
}

function showSlide(n) {
    const slides = document.querySelectorAll('.slide');
    const dots = document.querySelectorAll('.dot');
    const totalSlides = slides.length;
    
    if (n >= totalSlides) currentSlideIndex = 0;
    else if (n < 0) currentSlideIndex = totalSlides - 1;
    else currentSlideIndex = n;

    slides.forEach((slide, index) => {
        slide.classList.remove('active');
        if (index === currentSlideIndex) {
            slide.classList.add('active');
        }
    });

    dots.forEach((dot, index) => {
        dot.classList.remove('active');
        if (index === currentSlideIndex) {
            dot.classList.add('active');
        }
    });
}

function changeSlide(direction) {
    const slides = document.querySelectorAll('.slide');
    const totalSlides = slides.length;
    currentSlideIndex += direction;
    if (currentSlideIndex >= totalSlides) currentSlideIndex = 0;
    if (currentSlideIndex < 0) currentSlideIndex = totalSlides - 1;
    showSlide(currentSlideIndex);
}

function goToSlide(n) {
    showSlide(n - 1);
}

// Галерея ИИ
let currentAISlide = 0;

function showAISlide(n) {
    const aiSlides = document.querySelectorAll('.ai-slide');
    const totalAISlides = aiSlides.length;
    
    if (totalAISlides === 0) return;
    
    if (n >= totalAISlides) currentAISlide = 0;
    else if (n < 0) currentAISlide = totalAISlides - 1;
    else currentAISlide = n;

    aiSlides.forEach((slide, index) => {
        slide.classList.remove('active');
        if (index === currentAISlide) {
            slide.classList.add('active');
        }
    });

    // обновление счетчика
    const currentSlideElement = document.getElementById('current-ai-slide');
    const totalSlidesElement = document.getElementById('total-ai-slides');
    if (currentSlideElement) {
        currentSlideElement.textContent = currentAISlide + 1;
    }
    if (totalSlidesElement) {
        totalSlidesElement.textContent = totalAISlides;
    }
}

function changeAISlide(direction) {
    const aiSlides = document.querySelectorAll('.ai-slide');
    const totalAISlides = aiSlides.length;
    currentAISlide += direction;
    if (currentAISlide >= totalAISlides) currentAISlide = 0;
    if (currentAISlide < 0) currentAISlide = totalAISlides - 1;
    showAISlide(currentAISlide);
}

// кнопка вверх
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'instant'
    });
}

// чат
function toggleChat() {
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.classList.toggle('active');
    }
}

let chatHistory = [
    {
        role: 'system',
        content: 'Ты дружелюбный ассистент компании Pizz. Отвечай кратко и по делу, помогай с тарифами и продуктом.'
    }
];

let chatPending = false;

async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const chatMessages = document.getElementById('chatMessages');
    
    if (!chatInput || !chatMessages) return;
    
    const message = chatInput.value.trim();
    if (message === '' || chatPending) return;

    const userMessage = document.createElement('div');
    userMessage.className = 'chat-message user';
    userMessage.innerHTML = `<p>${message}</p>`;
    chatMessages.appendChild(userMessage);

    chatHistory.push({ role: 'user', content: message });
    chatInput.value = '';
    chatMessages.scrollTop = chatMessages.scrollHeight;

    const typingMessage = document.createElement('div');
    typingMessage.className = 'chat-message bot typing';
    typingMessage.innerHTML = `<p>Ассистент печатает...</p>`;
    chatMessages.appendChild(typingMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    chatPending = true;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ messages: chatHistory })
        });

        const data = await response.json();

        if (!response.ok || !data.reply) {
            throw new Error(data.error || 'Ошибка сервера');
        }

        typingMessage.innerHTML = `<p>${data.reply}</p>`;
        typingMessage.classList.remove('typing');
        chatHistory.push({ role: 'assistant', content: data.reply });
    } catch (error) {
        typingMessage.innerHTML = `<p>Не удалось получить ответ. Попробуйте ещё раз.</p>`;
        typingMessage.classList.remove('typing');
        console.error(error);
    } finally {
        chatPending = false;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function handleChatKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

// FAQ аккордеон
document.addEventListener('DOMContentLoaded', function() {
    const faqItems = document.querySelectorAll('.faq-item');
    
    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        if (question) {
            question.addEventListener('click', () => {
                // Закрытие других открытых элементов
                faqItems.forEach(otherItem => {
                    if (otherItem !== item) {
                        otherItem.classList.remove('active');
                    }
                });
                // Переключение текущего элемента
                item.classList.toggle('active');
            });
        }
    });

    // Инициализация слайдеров только если они есть на странице
    const slides = document.querySelectorAll('.slide');
    if (slides.length > 0) {
        initSlider();
    }
    
    const aiSlides = document.querySelectorAll('.ai-slide');
    if (aiSlides.length > 0) {
        showAISlide(0);
    }
});

// Плавная прокрутка для якорных ссылок
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Показ/скрытие кнопок прокрутки при скролле
window.addEventListener('scroll', function() {
    const scrollButtons = document.querySelector('.scroll-buttons');
    if (scrollButtons) {
        if (window.pageYOffset > 300) {
            scrollButtons.style.opacity = '1';
            scrollButtons.style.visibility = 'visible';
        } else {
            scrollButtons.style.opacity = '0.7';
        }
    }
});

// Floorplan styles switcher
document.addEventListener('DOMContentLoaded', function() {
    const iframe = document.querySelector('#floorplan-frame');
    if (!iframe) return;

    const urls = {
        scandy: "https://getfloorplan.com/widget/?id=95556aeb-a049-43eb-8199-48ef264e4ffb&type=living&style=scandy&lang=en",
        boho: "https://getfloorplan.com/widget/?id=dcfe17df-8d21-4750-a9cc-105ebd01ab82&type=living&style=boho&lang=en",
        england: "https://getfloorplan.com/widget/?id=38bb1c6d-d0b2-4361-a249-6a53fa1d2792&type=living&style=england&lang=en",
        zero: "https://getfloorplan.com/widget/?id=331f74b4-c279-4e4a-b3da-6d996516f674&type=living&style=zero&lang=en",
        modern: "https://getfloorplan.com/widget/?id=b0d7b7e2-1e09-4eff-a6dc-67533c930947&type=living&style=modern&lang=en",
        japandi: "https://getfloorplan.com/widget/?id=a82ee6b2-35b9-401f-afec-802fe3cd7cb8&type=living&style=japandi&lang=en",
        elegance: "https://getfloorplan.com/widget/?id=7d3e90ca-cc48-4e36-8cfa-c5b1652ce92d&type=living&style=elegance&lang=en",
        american: "https://getfloorplan.com/widget/?id=ebded98e-61e8-4a8e-891c-d8f0f2a62f8c&type=living&style=american&lang=en"
    };

    document.querySelectorAll('input[name="style"]').forEach(radio => {
        radio.addEventListener('change', () => {
            if (urls[radio.value]) {
                iframe.src = urls[radio.value];
            }
        });
    });
});

