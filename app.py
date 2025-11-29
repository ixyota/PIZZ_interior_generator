import logging
import os
import re
import smtplib
import uuid
from datetime import datetime
from email.message import EmailMessage

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash
from openai import OpenAI
from generator_utils import generate_interior, get_style_prompt

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'changeme-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['RESULT_FOLDER'] = os.path.join(BASE_DIR, 'results')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

logger = logging.getLogger(__name__)
PASSWORD_PATTERN = re.compile(r'^[A-Za-z0-9]{8,}$')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
openai_api_key = os.getenv('OPENAI_API_KEY')
openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

PLANS = {
    'basic': {'name': 'Basic Set', 'price': '25$', 'description': '2D / 3D'},
    'plus': {
        'name': 'Plus Set',
        'price': '45$',
        'description': '2D / 3D / Тур / High Quality',
    },
    'render': {
        'name': 'Render Set',
        'price': '49$',
        'description': '2D / 3D / Тур / High Quality / Визуализации',
    },
    'max': {
        'name': 'Max Set',
        'price': '69$',
        'description': 'Full пакет + Брендинг',
    },
    'pro': {'name': 'Pro Set', 'price': '49$', 'description': '2D / 3D / Тур / Брендинг'},
}


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_slug = db.Column(db.String(32), nullable=False)
    plan_name = db.Column(db.String(64), nullable=False)
    card_holder = db.Column(db.String(128), nullable=False)
    card_number = db.Column(db.String(24), nullable=False)
    expiry_month = db.Column(db.String(2), nullable=False)
    expiry_year = db.Column(db.String(4), nullable=False)
    cvv = db.Column(db.String(4), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('subscriptions', lazy=True))


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def validate_password(password: str) -> bool:
    """Пароль минимум 8 символов, только латиница и цифры."""
    if not password:
        return False
    return bool(PASSWORD_PATTERN.fullmatch(password))


def get_plan_by_slug(slug: str):
    if not slug:
        return None
    return PLANS.get(slug.lower())


def send_contact_email(first_name: str, last_name: str, email: str, message: str) -> None:
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    recipient = os.getenv('CONTACT_EMAIL_TO') or smtp_username
    use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'

    if not all([smtp_server, smtp_port, smtp_username, smtp_password, recipient]):
        raise RuntimeError(
            'SMTP настройки не заданы. Установите SMTP_SERVER, SMTP_PORT, '
            'SMTP_USERNAME, SMTP_PASSWORD и CONTACT_EMAIL_TO.'
        )

    email_body = (
        f"Новое сообщение с сайта Pizz:\n\n"
        f"Имя: {first_name}\n"
        f"Фамилия: {last_name or '—'}\n"
        f"Email отправителя: {email}\n\n"
        f"Сообщение:\n{message}"
    )

    msg = EmailMessage()
    msg['Subject'] = 'Контактная форма Pizz'
    msg['From'] = smtp_username
    msg['To'] = recipient
    msg['Reply-To'] = email
    msg.set_content(email_body)

    with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
        if use_tls:
            server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)


def init_app():
    """Инициализация приложения (миграции, подготовка БД и т.д.)."""
    with app.app_context():
        db.create_all()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([first_name, email, password, confirm_password]):
            flash('Заполните обязательные поля.', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Пароли не совпадают.', 'error')
            return render_template('register.html')

        if not validate_password(password):
            flash(
                'Пароль должен содержать минимум 8 символов и состоять только из латинских букв и цифр.',
                'error',
            )
            return render_template('register.html')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Пользователь с таким email уже существует.', 'error')
            return render_template('register.html')

        new_user = User(first_name=first_name, last_name=last_name, email=email)
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            logger.exception('Ошибка при сохранении пользователя: %s', exc)
            flash('Не удалось завершить регистрацию. Попробуйте позже.', 'error')
            return render_template('register.html')

        flash('Регистрация успешна! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Вход выполнен успешно!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))

        flash('Неверный email или пароль.', 'error')
        return render_template('login.html')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из аккаунта.', 'success')
    return redirect(url_for('index'))


@app.route('/contact', methods=['GET', 'POST'])
@login_required
def contact():
    if request.method == 'POST':
        message = request.form.get('message', '').strip()

        if not message:
            flash('Пожалуйста, напишите сообщение.', 'error')
            return render_template('contact.html')

        try:
            send_contact_email(
                current_user.first_name,
                current_user.last_name,
                current_user.email,
                message,
            )
        except Exception as exc:
            logger.exception('Не удалось отправить письмо: %s', exc)
            flash('Не удалось отправить сообщение. Проверьте настройки почты и попробуйте снова.', 'error')
            return render_template('contact.html')

        flash('Ваше сообщение отправлено! Мы свяжемся с вами в ближайшее время.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html')


@app.route('/subscribe', methods=['GET', 'POST'])
@login_required
def subscribe():
    plan_slug = request.args.get('plan') or request.form.get('plan')
    plan = get_plan_by_slug(plan_slug)
    if not plan:
        flash('Выберите тариф перед оформлением подписки.', 'error')
        return redirect(url_for('index'))
    plan_slug = plan_slug.lower()

    if request.method == 'POST':
        card_holder = request.form.get('card_holder', '').strip()
        card_number = request.form.get('card_number', '').strip()
        expiry_month = request.form.get('expiry_month', '').strip()
        expiry_year = request.form.get('expiry_year', '').strip()
        cvv = request.form.get('cvv', '').strip()

        if not all([card_holder, card_number, expiry_month, expiry_year, cvv]):
            flash('Заполните все поля банковской карты.', 'error')
            return render_template('subscribe.html', plan=plan, plan_slug=plan_slug, form_data=request.form)

        errors = []

        if not re.fullmatch(r'[A-Za-z ]{2,64}', card_holder):
            errors.append('Имя владельца карты нужно вводить латинскими буквами.')

        if not re.fullmatch(r'\d{16}', card_number):
            errors.append('Номер карты должен содержать ровно 16 цифр.')

        if not re.fullmatch(r'\d{2}', expiry_month) or not (1 <= int(expiry_month) <= 12):
            errors.append('Месяц истечения карты укажите в формате MM (01-12).')

        if not re.fullmatch(r'\d{4}', expiry_year):
            errors.append('Год истечения карты укажите в формате YYYY.')

        if not re.fullmatch(r'\d{3}', cvv):
            errors.append('CVV/CVC должен содержать ровно 3 цифры.')

        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template('subscribe.html', plan=plan, plan_slug=plan_slug, form_data=request.form)

        subscription = Subscription(
            user_id=current_user.id,
            plan_slug=plan_slug.lower(),
            plan_name=plan['name'],
            card_holder=card_holder,
            card_number=card_number,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            cvv=cvv,
        )

        try:
            db.session.add(subscription)
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            logger.exception('Ошибка при сохранении подписки: %s', exc)
            flash('Не удалось оформить подписку. Попробуйте позже.', 'error')
            return render_template('subscribe.html', plan=plan, plan_slug=plan_slug, form_data=request.form)

        flash('Проверяем данные, подождите, мы напишем вам.', 'success')
        return redirect(url_for('index'))

    return render_template('subscribe.html', plan=plan, plan_slug=plan_slug, form_data=None)


@app.route('/chat', methods=['POST'])
def chat():
    payload = request.get_json(silent=True) or {}
    messages = payload.get('messages')

    if not messages:
        return jsonify({'error': 'Сообщение не должно быть пустым.'}), 400

    if not openai_client:
        return jsonify({'error': 'OpenAI API не настроен.'}), 500

    try:
        # Формируем список сообщений для OpenAI API
        chat_messages = [
            {'role': msg.get('role', 'user'), 'content': msg.get('content', '')} 
            for msg in messages
        ]
        
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=chat_messages,
        )
        ai_reply = response.choices[0].message.content
        return jsonify({'reply': ai_reply})
    except Exception as exc:
        logger.exception('Ошибка OpenAI: %s', exc)
        return jsonify({'error': 'Не удалось получить ответ ассистента. Попробуйте позже.'}), 500


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        # Здесь должна быть логика отправки email для восстановления пароля
        flash('Инструкции по восстановлению пароля отправлены на ваш email.', 'success')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')


@app.route('/generate', methods=['GET', 'POST'])
def generate():
    # Создаем папки для загрузок и результатов, если их нет
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)
    
    if request.method == 'POST':
        # Проверяем наличие файла
        if 'blueprint' not in request.files:
            return render_template('generate.html', error='Файл не был загружен.')
        
        blueprint_file = request.files['blueprint']
        if blueprint_file.filename == '':
            return render_template('generate.html', error='Файл не был выбран.')
        
        style = request.form.get('style', 'scandinavian')
        user_prompt = request.form.get('prompt', '').strip()
        
        # Получаем промпт для стиля
        style_prompt = get_style_prompt(style)
        if user_prompt:
            prompt = f"{style_prompt}\nAdditional requirements: {user_prompt}".strip()
        else:
            prompt = style_prompt
        
        # Сохраняем загруженный файл
        unique_id = uuid.uuid4().hex
        file_ext = os.path.splitext(blueprint_file.filename)[1]
        upload_filename = f"blueprint_{unique_id}{file_ext}"
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_filename)
        blueprint_file.save(upload_path)
        
        # Генерируем результат
        result_filename = f"result_{unique_id}.webp"
        result_path = os.path.join(app.config['RESULT_FOLDER'], result_filename)
        
        try:
            generated = generate_interior(prompt, upload_path, result_path, style, BASE_DIR)
            
            if generated:
                context = {
                    'result_url': f"/results/{result_filename}",
                    'source_url': f"/uploads/{upload_filename}",
                }
                return render_template('result.html', **context)
            else:
                return render_template('generate.html', error='Ошибка генерации. Проверьте ключ API.')
        except Exception as e:
            logger.exception('Ошибка при генерации интерьера: %s', e)
            return render_template('generate.html', error=f'Ошибка генерации: {str(e)}')
    
    return render_template('generate.html')


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/results/<filename>')
def result_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['RESULT_FOLDER'], filename)

init_app()


if __name__ == '__main__':
    app.run(debug=True)

