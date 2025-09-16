import sqlite3
import logging
from contextlib import contextmanager
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ===================== Logging =====================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ValourMatchBot")

def user_display(update: Update) -> str:
    """Readable username for logs/messages."""
    u = update.effective_user
    return f"@{u.username}" if u.username else f"{u.first_name} ({u.id})"


# ===================== Bot Token =====================
import os
TOKEN = os.getenv("TOKEN")


# ===================== Database =====================
conn = sqlite3.connect("valourmatch.db", check_same_thread=False)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Improve reliability/perf
cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("PRAGMA synchronous=NORMAL;")

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id       INTEGER PRIMARY KEY,
    name              TEXT NOT NULL,
    age               INTEGER NOT NULL,
    description       TEXT NOT NULL,
    photo_id          TEXT NOT NULL,
    gender            TEXT NOT NULL,           -- "Male" | "Female"
    preferred_gender  TEXT NOT NULL            -- "Male" | "Female"
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS likes (
    liker_id INTEGER NOT NULL,
    liked_id INTEGER NOT NULL,
    UNIQUE(liker_id, liked_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS skips (
    skipper_id INTEGER NOT NULL,
    skipped_id INTEGER NOT NULL,
    UNIQUE(skipper_id, skipped_id)
)
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_users_gender ON users(gender);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_likes_liker ON likes(liker_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_skips_skipper ON skips(skipper_id);")
conn.commit()

@contextmanager
def db():
    """Ensure commits and avoid leaving transactions open."""
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ===================== Keyboards =====================
GENDER_KB = ReplyKeyboardMarkup([["Male", "Female"]], resize_keyboard=True, one_time_keyboard=True)
GENDER_OR_KEEP_KB = ReplyKeyboardMarkup(
    [["Male", "Female"], ["🟰 Keep current"]],
    resize_keyboard=True,
    one_time_keyboard=True,
)
PHOTO_OR_KEEP_KB = ReplyKeyboardMarkup(
    [["🟰 Keep current"]],
    resize_keyboard=True,
    one_time_keyboard=True,
)
MENU_KB = ReplyKeyboardMarkup(
    [["View Profile", "Edit Profile"],
     ["Find a Match", "Delete Profile"]],
    resize_keyboard=True,
)
MATCH_KB = ReplyKeyboardMarkup(
    [["❤️ Like", "👎 Skip", "💤 Stop"]],
    resize_keyboard=True,
    one_time_keyboard=True,
)


# ===================== Conversation States =====================
ASK_NAME, ASK_AGE, ASK_DESC, ASK_PHOTO, ASK_GENDER, ASK_PREF_GENDER, MATCHING = range(7)


# ===================== DB helpers =====================
def get_user_row(tid: int):
    with db() as c:
        c.execute("SELECT * FROM users WHERE telegram_id=?", (tid,))
        return c.fetchone()

def has_liked(uid: int, oid: int) -> bool:
    with db() as c:
        c.execute("SELECT 1 FROM likes WHERE liker_id=? AND liked_id=?", (uid, oid))
        return c.fetchone() is not None

def has_skipped(uid: int, oid: int) -> bool:
    with db() as c:
        c.execute("SELECT 1 FROM skips WHERE skipper_id=? AND skipped_id=?", (uid, oid))
        return c.fetchone() is not None


# ===================== Error handler =====================
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled exception", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("😵 Oops, something went wrong. Please try again!")
    except Exception:
        pass


# ===================== Start / Help / Menu =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("%s used /start", user_display(update))
    urow = get_user_row(update.effective_user.id)
    if urow is None:
        await update.message.reply_text("Welcome! Let's set up your profile first. 👇", reply_markup=ReplyKeyboardRemove())
        await update.message.reply_text("1/6 — What’s your name?")
        context.user_data.clear()
        context.user_data["editing"] = False
        return ASK_NAME
    else:
        await update.message.reply_text("Welcome back! Choose an option:", reply_markup=MENU_KB)
        return ConversationHandler.END

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/start — Open the menu / register if new\n"
        "Use the menu buttons to view, edit, match, or delete your profile.",
        reply_markup=MENU_KB
    )

async def unknown_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I didn’t get that — use the menu below. 👇", reply_markup=MENU_KB)


# ===================== Edit Profile =====================
async def edit_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urow = get_user_row(update.effective_user.id)
    if urow is None:
        await update.message.reply_text("You don’t have a profile yet. Use /start to create one.", reply_markup=MENU_KB)
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["editing"] = True
    # seed existing values so user can “keep current”
    context.user_data["name"] = urow["name"]
    context.user_data["age"] = urow["age"]
    context.user_data["description"] = urow["description"]
    context.user_data["photo_id"] = urow["photo_id"]
    context.user_data["gender"] = urow["gender"]
    context.user_data["preferred_gender"] = urow["preferred_gender"]

    logger.info("%s started editing profile", user_display(update))
    await update.message.reply_text(
        "Editing your profile. Send new values, or choose 🟰 Keep current where offered.",
        reply_markup=ReplyKeyboardRemove()
    )
    await update.message.reply_text(
        f"1/6 — Current name: {urow['name']}\nSend a new name, or press 🟰 Keep current.",
        reply_markup=ReplyKeyboardMarkup([["🟰 Keep current"]], resize_keyboard=True, one_time_keyboard=True)
    )
    return ASK_NAME


# ===================== Registration / Edit Steps =====================
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text and text != "🟰 Keep current":
        context.user_data["name"] = text
    await update.message.reply_text("2/6 — Enter your age (numbers only):")
    return ASK_AGE

async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if context.user_data.get("editing") and text == "🟰 Keep current":
        pass
    else:
        if not text.isdigit():
            await update.message.reply_text(
                "Please enter a valid age (numbers only), or press 🟰 Keep current.",
                reply_markup=ReplyKeyboardMarkup([["🟰 Keep current"]], resize_keyboard=True, one_time_keyboard=True)
            )
            return ASK_AGE
        age = int(text)
        if age < 16 or age > 120:
            await update.message.reply_text("Age must be between 16 and 120.")
            return ASK_AGE
        context.user_data["age"] = age

    await update.message.reply_text(
        "3/6 — Write a short description about yourself (or press 🟰 Keep current).",
        reply_markup=ReplyKeyboardMarkup([["🟰 Keep current"]], resize_keyboard=True, one_time_keyboard=True)
    )
    return ASK_DESC

async def ask_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if context.user_data.get("editing") and text == "🟰 Keep current":
        pass
    else:
        context.user_data["description"] = text

    if context.user_data.get("editing"):
        await update.message.reply_text(
            "4/6 — Send a profile photo, or press 🟰 Keep current.",
            reply_markup=ReplyKeyboardMarkup([["🟰 Keep current"]], resize_keyboard=True, one_time_keyboard=True)
        )
    else:
        await update.message.reply_text("4/6 — Send a profile photo (required):")
    return ASK_PHOTO

async def ask_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("editing") and update.message.text == "🟰 Keep current":
        pass
    elif update.message.photo:
        context.user_data["photo_id"] = update.message.photo[-1].file_id
    else:
        if context.user_data.get("editing"):
            await update.message.reply_text("Send a new photo, or press 🟰 Keep current.", reply_markup=PHOTO_OR_KEEP_KB)
        else:
            await update.message.reply_text("A profile photo is required. Please send a photo.")
        return ASK_PHOTO

    if context.user_data.get("editing"):
        await update.message.reply_text("5/6 — Select your gender (or 🟰 Keep current):", reply_markup=GENDER_OR_KEEP_KB)
    else:
        await update.message.reply_text("5/6 — Select your gender:", reply_markup=GENDER_KB)
    return ASK_GENDER

async def ask_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text in ("Male", "Female"):
        context.user_data["gender"] = text
    elif text == "🟰 Keep current" and context.user_data.get("editing"):
        pass
    else:
        kb = GENDER_OR_KEEP_KB if context.user_data.get("editing") else GENDER_KB
        await update.message.reply_text("Please choose Male or Female.", reply_markup=kb)
        return ASK_GENDER

    if context.user_data.get("editing"):
        await update.message.reply_text("6/6 — Preferred gender to see (or 🟰 Keep current):", reply_markup=GENDER_OR_KEEP_KB)
    else:
        await update.message.reply_text("6/6 — Preferred gender to see:", reply_markup=GENDER_KB)
    return ASK_PREF_GENDER

async def ask_pref_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text in ("Male", "Female"):
        context.user_data["preferred_gender"] = text
    elif text == "🟰 Keep current" and context.user_data.get("editing"):
        pass
    else:
        kb = GENDER_OR_KEEP_KB if context.user_data.get("editing") else GENDER_KB
        await update.message.reply_text("Please choose Male or Female.", reply_markup=kb)
        return ASK_PREF_GENDER

    # Save to DB
    tid = update.effective_user.id
    payload = (
        tid,
        context.user_data["name"],
        context.user_data["age"],
        context.user_data["description"],
        context.user_data["photo_id"],
        context.user_data["gender"],
        context.user_data["preferred_gender"],
    )
    with db() as c:
        if get_user_row(tid) is None:
            c.execute("""
                INSERT INTO users
                (telegram_id, name, age, description, photo_id, gender, preferred_gender)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, payload)
        else:
            c.execute("""
                UPDATE users
                SET name=?, age=?, description=?, photo_id=?, gender=?, preferred_gender=?
                WHERE telegram_id=?
            """, (
                context.user_data["name"],
                context.user_data["age"],
                context.user_data["description"],
                context.user_data["photo_id"],
                context.user_data["gender"],
                context.user_data["preferred_gender"],
                tid
            ))
    logger.info("%s saved/updated their profile", user_display(update))
    await update.message.reply_text("✅ Profile saved!", reply_markup=MENU_KB)
    return ConversationHandler.END


# ===================== View Profile =====================
async def view_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urow = get_user_row(update.effective_user.id)
    if urow is None:
        await update.message.reply_text("You don't have a profile yet. Use /start to create one.", reply_markup=MENU_KB)
        return
    if not urow["photo_id"]:
        await update.message.reply_text(
            f"Name: {urow['name']}\nAge: {urow['age']}\nBio: {urow['description']}\n"
            f"Gender: {urow['gender']}\nPrefers: {urow['preferred_gender']}",
            reply_markup=MENU_KB
        )
        return
    await update.message.reply_photo(
        photo=urow["photo_id"],
        caption=(
            f"Name: {urow['name']}\nAge: {urow['age']}\nBio: {urow['description']}\n"
            f"Gender: {urow['gender']}\nPrefers: {urow['preferred_gender']}"
        ),
        reply_markup=MENU_KB
    )


# ===================== Matching =====================
async def find_match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ENTRY POINT into ConversationHandler for matching."""
    me = get_user_row(update.effective_user.id)
    if me is None:
        await update.message.reply_text("Register first using /start.", reply_markup=MENU_KB)
        return ConversationHandler.END

    with db() as c:
        c.execute(
            "SELECT * FROM users WHERE gender=? AND telegram_id!=?",
            (me["preferred_gender"], me["telegram_id"])
        )
        rows = c.fetchall()

    candidates = [
        r for r in rows
        if r["photo_id"] and not has_liked(me["telegram_id"], r["telegram_id"]) and not has_skipped(me["telegram_id"], r["telegram_id"])
    ]

    if not candidates:
        await update.message.reply_text("No new profiles to show 😔", reply_markup=MENU_KB)
        return ConversationHandler.END

    context.user_data["candidates"] = candidates
    context.user_data["idx"] = 0
    return await show_next_candidate(update, context)

async def show_next_candidate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    candidates = context.user_data.get("candidates", [])
    idx = context.user_data.get("idx", 0)

    if idx >= len(candidates):
        await update.message.reply_text("No more profiles 😔", reply_markup=MENU_KB)
        return ConversationHandler.END

    cand = candidates[idx]
    context.user_data["current_candidate_id"] = cand["telegram_id"]
    context.user_data["current_candidate_name"] = cand["name"]

    if not cand["photo_id"]:
        context.user_data["idx"] += 1
        return await show_next_candidate(update, context)

    await update.message.reply_photo(
        photo=cand["photo_id"],
        caption=f"Name: {cand['name']}\nAge: {cand['age']}\nBio: {cand['description']}",
        reply_markup=MATCH_KB
    )
    return MATCHING

async def match_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    my_id = update.effective_user.id
    my_disp = user_display(update)
    cand_id = context.user_data.get("current_candidate_id")
    cand_name = context.user_data.get("current_candidate_name", str(cand_id))

    if not cand_id:
        await update.message.reply_text("No active profile. Use ‘Find a Match’.", reply_markup=MENU_KB)
        return ConversationHandler.END

    # Accept both emoji and plain text
    is_like = text in ("❤️ Like", "Like", "👍 Like")
    is_skip = text in ("👎 Skip", "Skip", "No")
    is_stop = text in ("💤 Stop", "Stop")

    if is_like:
        with db() as c:
            c.execute("INSERT OR IGNORE INTO likes (liker_id, liked_id) VALUES (?, ?)", (my_id, cand_id))
        logger.info("%s liked %s (%s)", my_disp, cand_id, cand_name)

        with db() as c:
            c.execute("SELECT 1 FROM likes WHERE liker_id=? AND liked_id=?", (cand_id, my_id))
            mutual = c.fetchone() is not None

        if mutual:
            try:
                other_user = await context.bot.get_chat(cand_id)
                other_name = f"@{other_user.username}" if other_user.username else cand_name
            except Exception:
                other_name = cand_name

            me_live = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
            await update.message.reply_text(
                f"🎉 It's a match! You and {other_name} liked each other ❤️\nStart chatting now!"
            )
            try:
                await context.bot.send_message(
                    chat_id=cand_id,
                    text=f"🎉 It's a match! You and {me_live} liked each other ❤️\nStart chatting now!"
                )
            except Exception as e:
                logger.warning("Could not DM other user about the match: %s", e)

            logger.info("MATCH between %s and %s", my_disp, other_name)

    elif is_skip:
        with db() as c:
            c.execute("INSERT OR IGNORE INTO skips (skipper_id, skipped_id) VALUES (?, ?)", (my_id, cand_id))
        logger.info("%s skipped %s (%s)", my_disp, cand_id, cand_name)

    elif is_stop:
        logger.info("%s stopped matching", my_disp)
        await update.message.reply_text("Stopped matching.", reply_markup=MENU_KB)
        return ConversationHandler.END

    else:
        await update.message.reply_text("Use the buttons below. ❤️ Like • 👎 Skip • 💤 Stop", reply_markup=MATCH_KB)
        return MATCHING

    # Next candidate
    context.user_data["idx"] = context.user_data.get("idx", 0) + 1
    return await show_next_candidate(update, context)


# ===================== Delete Profile =====================
async def delete_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with db() as c:
        c.execute("DELETE FROM users WHERE telegram_id=?", (uid,))
        c.execute("DELETE FROM likes WHERE liker_id=? OR liked_id=?", (uid, uid))
        c.execute("DELETE FROM skips WHERE skipper_id=? OR skipped_id=?", (uid, uid))
    logger.info("%s deleted their profile", user_display(update))
    await update.message.reply_text("Your profile has been deleted.", reply_markup=MENU_KB)


# ===================== Main wiring =====================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_error_handler(on_error)

    # Conversation: registration/edit + matching (Find a Match is now an entry point!)
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^Edit Profile$"), edit_profile),
            MessageHandler(filters.Regex("^Find a Match$"), find_match),   # <-- important
            CommandHandler("find", find_match),                            # optional: /find command
        ],
        states={
            ASK_NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_AGE:         [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_age)],
            ASK_DESC:        [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_desc)],
            ASK_PHOTO:       [MessageHandler(filters.PHOTO | filters.Regex("^🟰 Keep current$"), ask_photo)],
            ASK_GENDER:      [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_gender)],
            ASK_PREF_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_pref_gender)],
            MATCHING:        [MessageHandler(filters.TEXT & ~filters.COMMAND, match_response)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )
    app.add_handler(conv)

    # Menu buttons outside the conversation
    app.add_handler(MessageHandler(filters.Regex("^View Profile$"), view_profile))
    app.add_handler(MessageHandler(filters.Regex("^Delete Profile$"), delete_profile))

    # Commands
    app.add_handler(CommandHandler("help", help_cmd))

    # Unknown text outside conversations -> show menu
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_fallback))

    logger.info("Bot starting…")
    app.run_polling()
