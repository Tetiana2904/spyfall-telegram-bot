from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
)
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, CallbackContext, JobQueue
)
import threading
import random
import json
import os

def load_stats():
    if os.path.exists("player_stats.json"):
        with open("player_stats.json", "r") as f:
            return json.load(f)
    return {}

def save_stats(stats):
    with open("player_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

TOKEN = '8160868856:AAG8XUDYboPUKuYL5V1-gah56LmRBZobYo4'

LOCATIONS = [
    "Аеропорт", "Кінотеатр", "Школа", "Пляж", "Ресторан",
    "Казино", "Цирк", "Готель", "Банк", "Поліція"
]

game_state = {
    'players': {},
    'is_running': False,
    'chat_id': None,
    'pinned_message_id': None,
    'votes': {},
    'vote_message_id': None,
    'stats_message_id': None,
    'discussion_message_id': None,
    'registration_job': None,
    'timer_job': None,
    'player_list_message_id': None,
    'vote_job': None,
    'time_left': 240,
    'reply_markup': None,
    'registration_started': False,
}

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Привіт! Це бот для гри Spyfall.\n\n"
        "Команди:\n"
        "/join — приєднатися до гри\n"
        "/startgame — почати гру\n"
        "/stopgame — зупинити гру\n"
        "/extend — продовжити час\n"
        "/leave — вийти з гри\n"
        "/moretime — додати ще 1 хвилину до реєстрації"
    )



def send_or_update_registration_message(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    players = game_state['players']
    time_left = game_state['time_left']

    player_names = [info['name'] for info in players.values()]
    players_text = "📢 Реєстрація триває!\n"
    players_text += "Зареєстровані:\n" + "\n".join(f"- {name}" for name in player_names)
    players_text += f"\n\n📋 Усього: {len(player_names)} гравців"
    players_text += f"\n⏳ До старту гри залишилось: {time_left} секунд"

    button = InlineKeyboardButton("➕ Приєднатися", callback_data="join")
    markup = InlineKeyboardMarkup([[button]])

    if game_state['player_list_message_id']:
        try:
            context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=game_state['player_list_message_id'],
                text=players_text,
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            print(f"❌ Не вдалося оновити повідомлення реєстрації: {e}")
    else:
        msg = context.bot.send_message(
            chat_id=chat_id,
            text=players_text,
            reply_markup=markup,
            parse_mode=ParseMode.MARKDOWN
        )
        game_state['player_list_message_id'] = msg.message_id
        pin_message(context, chat_id, msg.message_id)

def registration_tick(context: CallbackContext):
    if not game_state['registration_started']:
        return

    game_state['time_left'] -= 10

    if game_state['time_left'] <= 0:
        context.job.schedule_removal()
        fake_message = type('FakeMessage', (), {'chat_id': game_state['chat_id']})
        fake_update = Update(update_id=0, message=fake_message)
        startgame(fake_update, context)
        return

    update_registration_message(context)
def join(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    name = user.full_name

    if game_state['is_running']:
        update.message.reply_text("Гра вже почалася, не можна приєднатися.")
        return

    if user_id in game_state['players']:
        update.message.reply_text("Ти вже в грі.")
        return

    game_state['players'][user_id] = {'name': name, 'role': None, 'location': None}
    update.message.reply_text(f"{name} приєднався до гри!")

    # Якщо перша реєстрація — запускаємо таймер
    if not game_state['registration_started']:
        game_state['registration_started'] = True
        game_state['chat_id'] = update.message.chat_id
        game_state['time_left'] = 60  # ⏳ таймер реєстрації
        game_state['timer_job'] = context.job_queue.run_repeating(registration_tick, 10, context=game_state['chat_id'])

    # Надсилаємо/оновлюємо повідомлення
    send_or_update_registration_message(update, context)
def registration_button_callback(update: Update, context: CallbackContext):
    if update.callback_query.data == "join":
        update.callback_query.answer()
        update.message = update.callback_query.message
        join(update, context)

def pin_message(context: CallbackContext, chat_id, message_id):
    try:
        if game_state.get('pinned_message_id'):
            context.bot.unpin_chat_message(chat_id, game_state['pinned_message_id'])
        context.bot.pin_chat_message(chat_id, message_id)
        game_state['pinned_message_id'] = message_id
    except Exception as e:
        print(f"Не вдалося закріпити повідомлення: {e}")

def show_players_list(update: Update, context: CallbackContext):
    player_names = [info['name'] for info in game_state['players'].values()]
    players_text = "📢 Реєстрація триває!\nЗареєстровані:\n" + "\n".join(f"- {name}" for name in player_names)
    players_text += f"\n\nУсього {len(player_names)} гравців."

    button = InlineKeyboardButton("➕ Приєднатися", callback_data="join")
    markup = InlineKeyboardMarkup([[button]])
    if game_state['player_list_message_id']:
        try:
            context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=game_state['player_list_message_id'],
                text=players_text,
                reply_markup=markup
            )
        except Exception as e:
            print(f"❌ Не вдалося оновити повідомлення: {e}")
    else:
        msg = context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=players_text,
            reply_markup=markup
        )
        game_state['player_list_message_id'] = msg.message_id
        pin_message(context, update.effective_chat.id, msg.message_id)

def moretime(update: Update, context: CallbackContext):
    if not game_state['registration_started']:
        update.message.reply_text("Реєстрація ще не почалась.")
        return

    game_state['time_left'] += 60  # додаємо 1 хвилину
    update_registration_message(context)
    update.message.reply_text("⏱ Реєстрацію продовжено на 1 хвилину!")

def startgame_auto(context: CallbackContext):
    chat_id = context.job.context
    message = type('FakeMessage', (), {'chat_id': chat_id})
    fake_update = Update(update_id=0, message=message)
    startgame(fake_update, context)

def leave(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    if user_id in game_state['players']:
        name = game_state['players'][user_id]['name']
        del game_state['players'][user_id]
        update.message.reply_text(f"{name} вийшов з гри.")
    else:
        update.message.reply_text("Ти ще не в грі.")
    if game_state['is_running'] and len(game_state['players']) == 1:
        finish_game(context)

def startgame(update: Update, context: CallbackContext, spy_count=1):
    if game_state['is_running']:
        context.bot.send_message(chat_id=update.message.chat_id, text="Гра вже йде!")
        return
    if len(game_state['players']) < 2:
        context.bot.send_message(chat_id=update.message.chat_id, text="Потрібно мінімум 2 гравці.")
        return

    # ✅ Зупиняємо таймер реєстрації, якщо був
    game_state['registration_started'] = False
    if game_state['timer_job']:
        game_state['timer_job'].schedule_removal()
        game_state['timer_job'] = None

    game_state['is_running'] = True
    game_state['votes'].clear()
    game_state['time_left'] = 240

    players_ids = list(game_state['players'].keys())
    if spy_count >= len(players_ids):
        spy_count = max(1, len(players_ids) - 1)
    spy_ids = random.sample(players_ids, spy_count)
    location = random.choice(LOCATIONS)

    for pid in players_ids:
        if pid in spy_ids:
            game_state['players'][pid]['role'] = 'spy'
            game_state['players'][pid]['location'] = None
        else:
            game_state['players'][pid]['role'] = 'player'
            game_state['players'][pid]['location'] = location

    # 🧾 Формуємо список гравців
    players_text = ""
    for pid, info in game_state['players'].items():
        players_text += f"{info['name']} — 0 голосів\n"

    discussion_text = (
        "🗣 Обговорення триває!\n"
        f"⏳ Час залишився: {game_state['time_left']} секунд\n\n"
        "👥 Гравці:\n"
        f"{players_text}\n"
        f"📋 Всього {len(game_state['players'])} учасників"
    )

    button = InlineKeyboardButton("🔗 Перейти в бот", url="https://t.me/FamiliaAlDentebot")
    markup = InlineKeyboardMarkup([[button]])

    sent = context.bot.send_message(
        chat_id=update.message.chat_id,
        text=discussion_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup
    )
    game_state['discussion_message_id'] = sent.message_id
    pin_message(context, update.message.chat_id, sent.message_id)

    # 🕵️ Приватні ролі
    for pid, info in game_state['players'].items():
        role_text = "Я шпигун! 🤫" if info['role'] == 'spy' else f"Твоя локація: {info['location']}"
        try:
            context.bot.send_message(chat_id=pid, text=role_text)
        except:
            context.bot.send_message(chat_id=update.message.chat_id, text=f"⚠️ {info['name']}, дозволь боту писати тобі в особисті.")

    # ⏱ Таймери
    game_state['timer_job'] = context.job_queue.run_repeating(timer_tick, 10, context=update.message.chat_id)

    # ✅ Голосування за 20 секунд до кінця
    vote_time = max(10, game_state['time_left'] - 20)
    game_state['vote_job'] = context.job_queue.run_once(start_voting, vote_time, context=update.message.chat_id)

def choose_spy_count(update: Update, context: CallbackContext):
    if game_state['is_running']:
        update.message.reply_text("Гра вже йде!")
        return
    if len(game_state['players']) < 2:
        update.message.reply_text("Потрібно мінімум 2 гравці.")
        return

    buttons = [
        [InlineKeyboardButton("🕵️ Один шпигун", callback_data="spy_1")],
        [InlineKeyboardButton("🕵️🕵️ Два шпигуна", callback_data="spy_2")]
    ]
    markup = InlineKeyboardMarkup(buttons)
    update.message.reply_text("Скільки має бути шпигунів?", reply_markup=markup)

def spy_count_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    spy_count = int(query.data.split("_")[1])
    query.message.delete()
    fake_message = type('FakeMessage', (), {'chat_id': query.message.chat_id})
    fake_update = Update(update_id=0, message=fake_message)
    startgame(fake_update, context, spy_count=spy_count)

def start_voting(context: CallbackContext):
    if not game_state['is_running']:
        return  # ⛔ Якщо гра завершиласт рано
    chat_id = context.job.context
    vote_buttons = []
    for pid, info in game_state['players'].items():
        vote_buttons.append([InlineKeyboardButton(info['name'], callback_data=f"vote_{pid}")])
    vote_buttons.append([InlineKeyboardButton("+30 секунд", callback_data="extend_30")])
    markup = InlineKeyboardMarkup(vote_buttons)
    vote_message = context.bot.send_message(
        chat_id=chat_id,
        text="🗳 Голосування — виберіть, кого лінчувати:",
        reply_markup=markup
    )
    pin_message(context, chat_id, vote_message.message_id)
    game_state['vote_message_id'] = vote_message.message_id
    game_state['reply_markup'] = markup

def vote_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    voter_id = query.from_user.id
    data = query.data

    if not game_state['is_running']:
        query.answer("Гра неактивна.")
        return

    if data == "extend_30":
        game_state['time_left'] += 30
        query.answer("⏱ Час продовжено на 30 секунд!")
        return

    if not data.startswith("vote_"):
        query.answer()
        return

    target_id = int(data.split("_")[1])

    if target_id == voter_id:
        query.answer("Не можна голосувати за себе.")
        return

    if target_id not in game_state['players']:
        query.answer("Гравець не знайдений.")
        return

    game_state['votes'][voter_id] = target_id

    voted_name = game_state['players'][target_id]['name']
    query.answer(f"Ти проголосував за {voted_name}")

    # 🔁 Оновити повідомлення обговорення після кожного голосу
    update_discussion_message(context)

    # 🔚 Якщо більше половини вже проголосували — закінчуємо гру
    if len(game_state['votes']) > len(game_state['players']) // 2:
        finish_game(context)
def timer_tick(context: CallbackContext):
    chat_id = context.job.context

    if not game_state['is_running']:
        context.job.schedule_removal()
        return

    game_state['time_left'] -= 10

    if game_state['time_left'] <= 0:
        finish_game(context)
        return

    # 🔁 Оновити повідомлення обговорення (із голосами та часом)
    update_discussion_message(context)

def update_discussion_message(context: CallbackContext):
    chat_id = game_state['chat_id']
    time_left = game_state['time_left']
    players = game_state['players']
    votes = game_state['votes']

    # Голоси: {target_id: [від_кого1, від_кого2]}
    vote_map = {}
    for voter_id, target_id in votes.items():
        vote_map.setdefault(target_id, []).append(voter_id)

    players_text = ""
    for pid, info in players.items():
        name = info['name']
        vote_count = len(vote_map.get(pid, []))
        voters = vote_map.get(pid, [])
        voters_names = [players[vid]['name'] for vid in voters]
        if voters_names:
            players_text += f"{name} — {vote_count} голосів (від {', '.join(voters_names)})\n"
        else:
            players_text += f"{name} — 0 голосів\n"

    discussion_text = (
        "🗣 Обговорення триває!\n"
        f"⏳ Час залишився: {time_left} секунд\n\n"
        "👥 Гравці:\n"
        f"{players_text}\n"
        f"📋 Всього {len(players)} учасників"
    )

    button = InlineKeyboardButton("🔗 Перейти в бот", url="https://t.me/FamiliaAlDentebot")
    markup = InlineKeyboardMarkup([[button]])

    try:
        context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game_state['discussion_message_id'],
            text=discussion_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup
        )
    except Exception as e:
        print(f"❌ Не вдалося оновити обговорення: {e}")   

def finish_game(context: CallbackContext):
    if not game_state['is_running']:
        return

    chat_id = game_state['chat_id']

    vote_tally = {}
    for target_id in game_state['votes'].values():
        vote_tally[target_id] = vote_tally.get(target_id, 0) + 1

    lynched_id = max(vote_tally, key=vote_tally.get) if vote_tally else None
    spy_id = next((pid for pid, info in game_state['players'].items() if info['role'] == 'spy'), None)

    if lynched_id is None:
        text = "⏰ Час вийшов! Ніхто не був лінчений.\n"
    else:
        lynched_name = game_state['players'][lynched_id]['name']
        text = f"⏰ Час вийшов!\n\n👥 Лінчували — [{lynched_name}](tg://user?id={lynched_id}).\n"

    spy_name = game_state['players'][spy_id]['name']
    text += f"🕵️‍♂️ Шпигун — [{spy_name}](tg://user?id={spy_id})!\n\n🎉 Дякуємо за гру! Було 🔥 "

    context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
    try:
       context.bot.unpin_chat_message(chat_id, game_state['pinned_message_id'])
    except:
        pass
    stats = load_stats()
    for pid, info in game_state['players'].items():
        pid = str(pid)
        if pid not in stats:
            stats[pid] = {
                "name": info['name'],
                "games_played": 0,
                "spy_wins": 0
            }
        stats[pid]['games_played'] += 1
        if info['role'] == 'spy' and pid == str(spy_id):
            stats[pid]['spy_wins'] += 1
    save_stats(stats)
    game_state['is_running'] = False
    game_state['players'].clear()
    game_state['votes'].clear()
    game_state['player_list_message_id'] = None
    game_state['vote_message_id'] = None
    game_state['discussion_message_id'] = None
    game_state['chat_id'] = None
    game_state['reply_markup'] = None
    game_state['time_left'] = 240
    game_state['registration_started'] = False

def stopgame(update: Update, context: CallbackContext):
    if not game_state['is_running']:
        update.message.reply_text("Гра не йде.")
        return

    game_state['is_running'] = False
    game_state['players'].clear()
    game_state['votes'].clear()
    game_state['vote_message_id'] = None
    game_state['discussion_message_id'] = None
    game_state['chat_id'] = None
    game_state['reply_markup'] = None
    game_state['time_left'] = 240
    game_state['registration_started'] = False

    update.message.reply_text("Гру зупинено.")
def show_help(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🕵️‍♂️ *Spyfall — правила гри:*\n"
        "• Один із вас — *шпигун* (не знає локацію).\n"
        "• Інші — *гравці* (знають локацію).\n"
        "• Мета гравців — знайти шпигуна, шпигуна — не видати себе.\n\n"
        "🎙 *Обговорення:*\n"
        "• Ідете по списку зверху вниз.\n"
        "• Кожен задає 1 питання наступному гравцю.\n"
        "• Питання — загальні, без згадування самої локації.\n\n"
        "🧠 Відповідай обережно.\n"
        "🗳 За 10 секунд до кінця починається голосування — *швидко натисни на гравця*, якого підозрюєш.",
        parse_mode=ParseMode.MARKDOWN
    )


def show_stats(update: Update, context: CallbackContext):
    stats = load_stats()
    if not stats:
        update.message.reply_text("📉 Статистика ще порожня.")
        return

    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['games_played'], reverse=True)

    text = "🏆 *Топ гравців цього чату:*\n"
    for i, (pid, data) in enumerate(sorted_stats[:10], 1):
        name = data['name']
        games = data['games_played']
        wins = data['spy_wins']
        text += f"{i}. {name} — 🎮 {games} ігор | 🕵️ {wins} перемог шпигуном\n"

    if 'stats_message_id' in game_state:
        try:
            context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=game_state['stats_message_id'],
                text=text,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        except:
            pass

    msg = update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    game_state['stats_message_id'] = msg.message_id

    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
def update_registration_message(context: CallbackContext):
    chat_id = game_state['chat_id']
    players = game_state['players']
    time_left = game_state['time_left']

    player_names = [info['name'] for info in players.values()]
    players_text = "📢 Реєстрація триває!\n"
    players_text += "Зареєстровані:\n" + "\n".join(f"- {name}" for name in player_names)
    players_text += f"\n\n📋 Усього: {len(player_names)} гравців"
    players_text += f"\n⏳ До старту гри залишилось: {time_left} секунд"

    button = InlineKeyboardButton("➕ Приєднатися", callback_data="join")
    markup = InlineKeyboardMarkup([[button]])

    try:
        context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game_state['player_list_message_id'],
            text=players_text,
            reply_markup=markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"❌ Не вдалося оновити повідомлення реєстрації: {e}")
def extend(update: Update, context: CallbackContext):
    if not game_state['is_running']:
        update.message.reply_text("Гра ще не почалася або вже завершена.")
        return

    game_state['time_left'] += 30
    update.message.reply_text("⏱ Час продовжено на 30 секунд!")
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('join', join))
    dp.add_handler(CommandHandler('stopgame', stopgame))
    dp.add_handler(CommandHandler('extend', extend))
    dp.add_handler(CommandHandler('leave', leave))
    dp.add_handler(CommandHandler('selectspy', choose_spy_count))
    dp.add_handler(CommandHandler('startgame', lambda u, c: startgame(u, c, spy_count=1)))
    dp.add_handler(CommandHandler('help', show_help))
    dp.add_handler(CommandHandler('stats', show_stats))
    dp.add_handler(CommandHandler('moretime', moretime))
    dp.add_handler(CallbackQueryHandler(spy_count_callback, pattern=r'^spy_'))
    dp.add_handler(CallbackQueryHandler(vote_callback, pattern=r'^vote_'))
    dp.add_handler(CallbackQueryHandler(registration_button_callback))
    dp.add_handler(CallbackQueryHandler(vote_callback))  # повторно, якщо треба без pattern

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()