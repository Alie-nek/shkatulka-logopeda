let products = [];
const CART_KEY = 'shkatulka_cart';


function getCart() {
    const stored = localStorage.getItem(CART_KEY);
    return stored ? JSON.parse(stored) : [];
}

function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
    updateCartCounter();
}

function updateCartCounter() {
    const cart = getCart();
    const total = cart.length;  
    const counter = document.getElementById('cartCounter');
    if (counter) {
        counter.textContent = total;
        counter.style.opacity = total > 0 ? '1' : '0';
    }
}

function addToCart(product) {
    console.log('Добавляем товар:', product);
    let cart = getCart();
    const existing = cart.find(item => item.id === product.id);
    if (existing) {
        alert('Это пособие уже добавлено в корзину!');
        return;
    }
    
    let imagePath = product.image || 'static/img/placeholder.jpg';
    imagePath = imagePath.replace(/\\/g, '/');
    
    cart.push({ 
        id: product.id, 
        name: product.name, 
        price: product.price, 
        image: imagePath,
        quantity: 1
    });
    saveCart(cart);
    updateCartCounter();
    alert(`"${product.name}" добавлен в корзину!`);
}


async function loadProducts() {
    try {
        const response = await fetch('/api/products');
        products = await response.json();
        renderCatalog(products);
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        const container = document.getElementById('catalogContainer');
        if (container) container.innerHTML = '<div class="error">Ошибка загрузки товаров</div>';
    }
}

function renderCatalog(productsToRender) {
    const container = document.getElementById('catalogContainer');
    if (!container) return;
    container.innerHTML = '';

    if (productsToRender.length === 0) {
        container.innerHTML = '<div class="empty">Ничего не найдено</div>';
        return;
    }

    const grouped = {};
    productsToRender.forEach(p => {
        if (!grouped[p.category]) grouped[p.category] = [];
        grouped[p.category].push(p);
    });

    for (const [category, items] of Object.entries(grouped)) {
        const section = document.createElement('div');
        section.className = 'category-section';
        const title = document.createElement('h2');
        title.className = 'category-title';
        title.textContent = getCategoryName(category);
        const grid = document.createElement('div');
        grid.className = 'products-grid';
        items.forEach(product => {
            const card = createProductCard(product);
            grid.appendChild(card);
        });
        section.appendChild(title);
        section.appendChild(grid);
        container.appendChild(section);
    }
}

function getCategoryName(code) {
    const names = {
        'zvuki': 'Автоматизация звуков',
        'leksika': 'Лексическая тема',
        'slogovaia': 'Формирование слоговой структуры слова',
        'rech': 'Запуск речи',
        'work-programm': 'Рабочая программа учителя-логопеда'
    };
    return names[code] || code;
}

function createProductCard(product) {
    let imagePath = product.image || '/static/img/placeholder.jpg';
    imagePath = imagePath.replace(/\\/g, '/');
    
    const card = document.createElement('div');
    card.className = 'product-card';
    card.innerHTML = `
        <img class="product-image" src="${imagePath}" alt="${product.title}" onerror="this.src='/static/img/placeholder.jpg'">
        <div class="product-info">
            <h3 class="product-name">${product.title}</h3>
            <p class="product-description">${product.description}</p>
            <div class="product-price">${product.price} ₽</div>
            <button class="add-to-cart-btn" data-id="${product.id}" data-name="${product.title}" data-price="${product.price}">В корзину</button>
        </div>
    `;
    const btn = card.querySelector('.add-to-cart-btn');
    btn.addEventListener('click', () => addToCart({ 
        id: product.id, 
        name: product.title, 
        price: product.price, 
        image: imagePath  
    }));
    return card;
}


function initDropdown() {
    const dropdown = document.getElementById('dropdown');
    const dropdownBtn = document.getElementById('dropdownBtn');
    const dropdownMenu = document.getElementById('dropdownMenu');
    const selectedTheme = document.getElementById('selectedTheme');
    if (!dropdownBtn) return;
    dropdownBtn.addEventListener('click', (e) => { e.stopPropagation(); dropdown.classList.toggle('open'); });
    document.addEventListener('click', (e) => { if (dropdown && !dropdown.contains(e.target)) dropdown.classList.remove('open'); });
    if (dropdownMenu) {
        const items = dropdownMenu.querySelectorAll('li');
        items.forEach(item => {
            item.addEventListener('click', () => {
                items.forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                if (selectedTheme) selectedTheme.textContent = item.textContent;
                dropdown.classList.remove('open');
                const filterValue = item.dataset.value;
                applyFilter(filterValue);
            });
        });
    }
}

function applyFilter(filterValue) {
    if (!products.length) return;
    if (filterValue === 'all') {
        renderCatalog(products);
    } else {
        renderCatalog(products.filter(p => p.category === filterValue));
    }
}

function initSearch() {
    const searchForm = document.getElementById('searchForm');
    const searchInput = document.getElementById('searchInput');
    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const query = searchInput.value.toLowerCase();
            if (!products.length) return;
            renderCatalog(products.filter(p => p.title.toLowerCase().includes(query) || p.description.toLowerCase().includes(query)));
        });
    }
}


document.addEventListener('DOMContentLoaded', () => {
    loadProducts();
    initDropdown();
    initSearch();
    updateCartCounter();
});