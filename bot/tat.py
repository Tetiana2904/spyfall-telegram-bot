print("🧠 ЦЕ ТОЙ tat.py!")
import asyncio
import json
import os
import random
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, JobQueue
)

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

def load_stats():
    if os.path.exists("player_stats.json"):
        with open("player_stats.json", "r") as f:
            return json.load(f)
    return {}

def save_stats(stats):
    with open("player_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! Це бот для гри Spyfall.\n\n"
        "Команди:\n"
        "/join — приєднатися до гри\n"
        "/startgame — почати гру\n"
        "/stopgame — зупинити гру\n"
        "/extend — продовжити час\n"
        "/leave — вийти з гри\n"
        "/moretime — додати ще 1 хвилину до реєстрації"
    )


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    name = user.full_name

    if game_state['is_running']:
        await update.message.reply_text("Гра вже почалася, не можна приєднатися.")
        return

    if user_id in game_state['players']:
        await update.message.reply_text("Ти вже в грі.")
        return

    game_state['players'][user_id] = {'name': name, 'role': None, 'location': None}
    await update.message.reply_text(f"{name} приєднався до гри!")

    if not game_state['registration_started']:
        game_state['registration_started'] = True
        game_state['chat_id'] = update.effective_chat.id
        game_state['time_left'] = 60

        context.job_queue.run_repeating(
            registration_tick,
            interval=10,
            first=0,
            chat_id=game_state['chat_id'],
            name="registration_tick"
        )

    await send_or_update_registration_message(update, context)


async def registration_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "join":
        await query.answer()
        fake_update = Update(update_id=0, message=query.message)
        await join(fake_update, context)


async def send_or_update_registration_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=game_state['player_list_message_id'],
                text=players_text,
                reply_markup=markup,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            print(f"❌ Не вдалося оновити повідомлення реєстрації: {e}")
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=players_text,
            reply_markup=markup,
            parse_mode=ParseMode.MARKDOWN
        )
        game_state['player_list_message_id'] = msg.message_id
        await pin_message(context, chat_id, msg.message_id)


async def registration_tick(context: ContextTypes.DEFAULT_TYPE):
    if not game_state['registration_started']:
        return

    game_state['time_left'] -= 10

    if game_state['time_left'] <= 0:
        job = context.job
        if job:
            job.schedule_removal()

        fake_update = Update(update_id=0, message=type("FakeMessage", (), {
            "chat_id": game_state["chat_id"],
            "effective_chat": type("FakeChat", (), {"id": game_state["chat_id"]})
        }))
        await startgame(fake_update, context)
        return

    await update_registration_message(context)
async def moretime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_state['registration_started']:
        await update.message.reply_text("Реєстрація ще не почалась.")
        return

    game_state['time_left'] += 60
    await update_registration_message(context)
    await update.message.reply_text("⏱ Реєстрацію продовжено на 1 хвилину!")


async def update_registration_message(context: ContextTypes.DEFAULT_TYPE):
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
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game_state['player_list_message_id'],
            text=players_text,
            reply_markup=markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        print(f"❌ Не вдалося оновити повідомлення реєстрації: {e}")


async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    if user_id in game_state['players']:
        name = game_state['players'][user_id]['name']
        del game_state['players'][user_id]
        await update.message.reply_text(f"{name} вийшов з гри.")
    else:
        await update.message.reply_text("Ти ще не в грі.")
    if game_state['is_running'] and len(game_state['players']) == 1:
        await finish_game(context)


async def pin_message(context: ContextTypes.DEFAULT_TYPE, chat_id, message_id):
    try:
        if game_state.get('pinned_message_id'):
            await context.bot.unpin_chat_message(chat_id, game_state['pinned_message_id'])
        await context.bot.pin_chat_message(chat_id, message_id)
        game_state['pinned_message_id'] = message_id
    except Exception as e:
        print(f"❌ Не вдалося закріпити повідомлення: {e}")
async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE, spy_count=1):
    if game_state['is_running']:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Гра вже йде!")
        return

    if len(game_state['players']) < 2:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Потрібно мінімум 2 гравці.")
        return

    # 🛑 Зупинити реєстрацію
    game_state['registration_started'] = False
    if game_state['timer_job']:
        context.job_queue.scheduler.remove_job(game_state['timer_job'].name)
        game_state['timer_job'] = None

    game_state['is_running'] = True
    game_state['votes'].clear()
    game_state['time_left'] = 350
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

    game_state['chat_id'] = update.effective_chat.id

    # 🗣 Повідомлення обговорення
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

    sent = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=discussion_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup
    )
    game_state['discussion_message_id'] = sent.message_id
    await pin_message(context, update.effective_chat.id, sent.message_id)

    # 📬 Приватно надсилаємо ролі
    for pid, info in game_state['players'].items():
        role_text = "Я шпигун! 🤫" if info['role'] == 'spy' else f"Твоя локація: {info['location']}"
        try:
            await context.bot.send_message(chat_id=pid, text=role_text)
        except:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⚠️ {info['name']}, дозволь боту писати тобі в особисті.")

    # ⏱ Старт таймера
    game_state['timer_job'] = context.job_queue.run_repeating(timer_tick, interval=10, first=10, name="timer_tick", data=game_state['chat_id'])

    # 🗳 Старт голосування за 20 сек до кінця
    vote_time = max(10, game_state['time_left'] - 20)
    game_state['vote_job'] = context.job_queue.run_once(start_voting, when=vote_time, data=game_state['chat_id'])
async def choose_spy_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if game_state['is_running']:
        await update.message.reply_text("Гра вже йде!")
        return
    if len(game_state['players']) < 2:
        await update.message.reply_text("Потрібно мінімум 2 гравці.")
        return

    buttons = [
        [InlineKeyboardButton("🕵️ Один шпигун", callback_data="spy_1")],
        [InlineKeyboardButton("🕵️🕵️ Два шпигуна", callback_data="spy_2")]
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Скільки має бути шпигунів?", reply_markup=markup)

async def spy_count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    spy_count = int(query.data.split("_")[1])
    await query.message.delete()
    fake_message = type('FakeMessage', (), {'chat_id': query.message.chat_id})
    fake_update = Update(update_id=0, message=fake_message)
    await startgame(fake_update, context, spy_count=spy_count)

async def start_voting(context: ContextTypes.DEFAULT_TYPE):
    if not game_state['is_running']:
        return
    chat_id = context.job.data
    vote_buttons = []
    for pid, info in game_state['players'].items():
        vote_buttons.append([InlineKeyboardButton(info['name'], callback_data=f"vote_{pid}")])
    vote_buttons.append([InlineKeyboardButton("+30 секунд", callback_data="extend_30")])
    markup = InlineKeyboardMarkup(vote_buttons)
    vote_message = await context.bot.send_message(
        chat_id=chat_id,
        text="🗳 Голосування — виберіть, кого лінчувати:",
        reply_markup=markup
    )
    await pin_message(context, chat_id, vote_message.message_id)
    game_state['vote_message_id'] = vote_message.message_id
    game_state['reply_markup'] = markup

async def vote_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    voter_id = query.from_user.id
    data = query.data

    if not game_state['is_running']:
        await query.answer("Гра неактивна.")
        return

    if data == "extend_30":
        game_state['time_left'] += 30
        await query.answer("⏱ Час продовжено на 30 секунд!")
        return

    if not data.startswith("vote_"):
        await query.answer()
        return

    target_id = int(data.split("_")[1])

    if target_id == voter_id:
        await query.answer("Не можна голосувати за себе.")
        return

    if target_id not in game_state['players']:
        await query.answer("Гравець не знайдений.")
        return

    game_state['votes'][voter_id] = target_id
    voted_name = game_state['players'][target_id]['name']
    await query.answer(f"Ти проголосував за {voted_name}")

    # 🔄 Оновити повідомлення обговорення
    await update_discussion_message(context)

    if len(game_state['votes']) > len(game_state['players']) // 2:
        await finish_game(context)
async def timer_tick(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data

    if not game_state['is_running']:
        context.job.schedule_removal()
        return

    game_state['time_left'] -= 10

    if game_state['time_left'] <= 0:
        await finish_game(context)
        return

    await update_discussion_message(context)

async def update_discussion_message(context: ContextTypes.DEFAULT_TYPE):
    chat_id = game_state['chat_id']
    time_left = game_state['time_left']
    players = game_state['players']
    votes = game_state['votes']

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
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game_state['discussion_message_id'],
            text=discussion_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup
        )
    except Exception as e:
        print(f"❌ Не вдалося оновити обговорення: {e}")

async def finish_game(context: ContextTypes.DEFAULT_TYPE):
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
    text += f"🕵️‍♂️ Шпигун — [{spy_name}](tg://user?id={spy_id})!\n\n🎉 Дякуємо за гру! Було 🔥"

    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)

    try:
        await context.bot.unpin_chat_message(chat_id, game_state['pinned_message_id'])
    except:
        pass

    stats = load_stats()
    for pid, info in game_state['players'].items():
        pid_str = str(pid)
        if pid_str not in stats:
            stats[pid_str] = {
                "name": info['name'],
                "games_played": 0,
                "spy_wins": 0
            }
        stats[pid_str]['games_played'] += 1
        if info['role'] == 'spy' and pid == spy_id:
            stats[pid_str]['spy_wins'] += 1
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
async def stopgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_state['is_running']:
        await update.message.reply_text("Гра не йде.")
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

    await update.message.reply_text("Гру зупинено.")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕵️‍♂️ *Spyfall — правила гри:*\n"
        "• Один із вас — *шпигун* (не знає локацію).\n"
        "• Інші — *гравці* (знають локацію).\n"
        "• Мета гравців — знайти шпигуна, шпигуну — не видати себе.\n\n"
        "🎙 *Обговорення:*\n"
        "• Ідете по списку зверху вниз.\n"
        "• Кожен задає 1 питання наступному гравцю.\n"
        "• Питання — загальні, без згадування самої локації.\n\n"
        "🧠 Відповідай обережно.\n"
        "🗳 За 10 секунд до кінця починається голосування — *швидко натисни на гравця*, якого підозрюєш.",
        parse_mode=ParseMode.MARKDOWN
    )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = load_stats()
    if not stats:
        await update.message.reply_text("📉 Статистика ще порожня.")
        return

    sorted_stats = sorted(stats.items(), key=lambda x: x[1]['games_played'], reverse=True)

    text = "🏆 *Топ гравців цього чату:*\n"
    for i, (pid, data) in enumerate(sorted_stats[:10], 1):
        name = data['name']
        games = data['games_played']
        wins = data['spy_wins']
        text += f"{i}. {name} — 🎮 {games} ігор | 🕵️ {wins} перемог шпигуном\n"

    if game_state.get('stats_message_id'):
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=game_state['stats_message_id'],
                text=text,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        except:
            pass

    msg = await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    game_state['stats_message_id'] = msg.message_id

async def extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not game_state['is_running']:
        await update.message.reply_text("Гра ще не почалася або вже завершена.")
        return

    game_state['time_left'] += 30
    await update.message.reply_text("⏱ Час продовжено на 30 секунд!")

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("join", join))
    application.add_handler(CommandHandler("stopgame", stopgame))
    application.add_handler(CommandHandler("extend", extend))
    application.add_handler(CommandHandler("leave", leave))
    application.add_handler(CommandHandler("selectspy", choose_spy_count))
    application.add_handler(CommandHandler("startgame", lambda u, c: startgame(u, c, spy_count=1)))
    application.add_handler(CommandHandler("help", show_help))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("moretime", moretime))
    application.add_handler(CallbackQueryHandler(spy_count_callback, pattern=r"^spy_"))
    application.add_handler(CallbackQueryHandler(vote_callback, pattern=r"^vote_"))
    application.add_handler(CallbackQueryHandler(registration_button_callback))

    application.run_polling()

if __name__ == "__main__":
    main()

