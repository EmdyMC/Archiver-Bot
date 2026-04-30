import discord
import re

# Constants

MODERATOR_ID = 1161821342514036776
ARCHIVER_ID = 1162049503503863808
HELPER_ID = 1378983578251300934
ARCHIVED_DESIGNER = 1172971681527111700
SUBMITTER = 1172971622240620594
HIGHER_ROLES = {MODERATOR_ID, ARCHIVER_ID}
STAFF_ROLES = {MODERATOR_ID, ARCHIVER_ID,HELPER_ID}
NO_CHAT = 1390906563505684591
LOG_CHANNEL = 1343664979831820368 # Bot-logs
ARCHIVER_CHAT = 1163451952827478056
BOT_DM_THREAD = 1473708689461477641
NON_ARCHIVE_CATEGORIES = {1355756508394160229, 1184256131141484724, 1163087048173965402, 1378966923152195655, 1182932696662560798, 1374225342948053032, 1161803873317568583} # Archived, Voice, Public, Help, Staff, Decisions and Votes, Important
MAIN_ARCHIVE_CATEGORIES = {1162047368917692460, 1162048271393505440, 1162047650355482777, 1162355688014622800, 1162094819875762236, 1173052495346552892} #Monsters, Creatures, Agriculture, Blocks&Items, Item processing, Infrastructure
SUBMISSIONS_CHANNEL = 1161814713496256643
SUBMISSIONS_TRACKER_CHANNEL = 1394308822926889060
DEVELOPMENT_FORUM = 1420135695800074260
ALLOWED_FORUMS = {DEVELOPMENT_FORUM, SUBMISSIONS_CHANNEL}
SNAPSHOT_CHANNEL = 1353055573935132703
ARCHIVE_CORRECTIONS = 1284851559947305052
ARCHIVE_UPDATES = 1235473478371643412
HELP_FORUM = 1378037810975473846
FAQ_CHANNEL = 1365424262810177546
REJECTED_TAG = 1183092798908534804
ACCEPTED_TAG = 1183092754834788414
ARCHIVED_TAG = 1197302327065972776
INACTIVE_TAG = 1430378085332815872
UNSOLVED_TAG = 1378041211150929990
RESOLVED_TAGS = {REJECTED_TAG, ACCEPTED_TAG}
CLOSING_TAGS = {REJECTED_TAG, ARCHIVED_TAG}
PENDING_TAGS = {1257162647040819250, 1284913422487654612, 1378041211150929990, ACCEPTED_TAG} # Pending submissions, Pending corrections, Unsolved help
FORUMS = {SUBMISSIONS_CHANNEL, ARCHIVE_CORRECTIONS, HELP_FORUM}
TAG_COLOUR = {
    "Accepted": discord.Colour.green(),
    "Rejected": discord.Colour.red(),
    "Solved": discord.Colour.green(),
    "Archived": discord.Colour.dark_blue()} # Embed Colour based on tag
UPPER_TAGS = {"Accepted", "Rejected", "Solved", "Pending", "Archived"}
TESTING_EMOJI = "🧪"
CLOCK_EMOJI = "🕥"
CROSS_EMOJI = "❌"
ILLEGAL_COMPONENTS = {"@everyone", "@here"}
MESSAGES_LIST = "messages.json"
BLACKLIST = "blacklist.json"
DISCORD_CHAR_LIMIT = 1800
TIMEOUT_MESSAGE = """Your message on TMCC has been blocked as you failed to select the right onboarding option when joining the server (see below) and your account is suspected to be compromised.
    If you wish to partake in the server fully, make sure to select the correct option in the "Channels and Roles" section and follow the rules of the server."""
NO_CHAT_IMAGE = "https://cdn.discordapp.com/attachments/1315522702492172300/1466707151472033954/image.png"
SUBMISSION_PROMPT = """
- 📌 The submitter of the post can pin messages in the thread using the application command shown below. 
- ❌ This thread is for archival-related discussion only. No development or help questions are allowed.
- ⌚ Please be patient, as the archival team has a lot of posts to process. We will review this post as soon as possible."""
HOW_TO_PIN = "https://cdn.discordapp.com/attachments/1331670749471047700/1428615699378733108/how_to_pin.png"
HELP_FORUM_PROMPT = """
- ✅ The submitter of this question can mark posts as solved by using `/tag_selector` and selecting `✅ Solved`.
- 📖 Refer to the [guide](https://discord.com/channels/1161803566265143306/1378040485133680772) to get faster and better answers to your questions. Add any relevant information to your post.
- ⌚ Please be patient and polite. Remember that all helpers are volunteers."""
MENTION_RE = re.compile(r"<@!?(\d+)>")

# Embed text

OTHER_ARCHIVES = '''<:std:1399677131004580051> [**Storage Tech**](https://discord.gg/JufJ6uf) Item sorting and storage
<:std2:1469724306446614650> [**Storage Catalog**](https://discord.gg/hztJMTsx2m) Development-oriented storage tech
<:slime:1399677082472153098> [**Slimestone Tech Archive**](https://discord.gg/QQX5RBaHzK) Flying machines and movable contraptions
<:mtdr:1399677041946923061> [**Minecraft Tech Discord Recollector**](https://discord.gg/UT8ns46As9) Index of TMC SMP and archive servers
<:tnt:1399677165104009226> [**TNT Archive**](https://discord.gg/vPyUBcdmZV) TNT cannon tech and projectile physics
<:tree:1399677175803805696> [**Tree Huggers**](https://discord.gg/8bUbuuS) Tree farm development
<:hfh:1399677019767312404> [**Huge Fungi Huggers**](https://discord.gg/EKKkyfcPPV) Nether tree and foliage farm development
<:cart:1399676987928219739> [**Cartchives**](https://discord.gg/8nGNTewveC) Piston bolts and minecart based tech
<:wither:1399677185870008330> [**Wither Archive**](https://discord.gg/Ea28MyKB3J) Wither tech archive and development 
<:sos:1399677094169940139> [**Saints of Suppression**](https://discord.gg/xa7QWAeAng) Light and update suppression and skipping
<:aca:1399676962464600155> [**Autocrafting Archive**](https://discord.gg/guZdbQ9KQe) Crafters and modded autocrafting table tech
<:comp:1399677007406698516> [**Computational Minecraft Archive**](https://discord.gg/jSe4jR5Kx7) TMC-oriented computational redstone
<:tmcra:1399677154702135328> [**TMC Resources Archive**](https://discord.gg/E4q8WDUc7k) Compilation of TMC tricks, links, and resources
<:luke:1399677029707808768> [**Luke's Video Archive**](https://discord.gg/KTDacw6JYk) Chinese (BiliBili) tech recollector
<:ore:1399677056584781946> [**Open Redstone**](https://discord.gg/zjWRarN) (DiscOREd) Computational redstone community
<:squid:1399677105033183232> [**Piston Door Catalogue**](https://discord.gg/Khj8MyA) (Redstone Squid's Records Catalogue) Piston door index
<:ssf:1399677117884534875> [**Structureless Superflat Archive**](https://discord.gg/96Qm6e2AVH) (SSf Archive) Structureless superflat tech
<:rta:1399677071919288342> [**Russian Technical Minecraft Catalogue**](https://discord.com/invite/bMZYHnXnCA) (RTMC Каталог) Russian TMC archive
<:tba:1399677142660546620> [**Technical Bedrock Archive**](https://discord.com/invite/technical-bedrock-archive-715182000440475648) Bedrock TMC archive'''

COMMANDS_LIST = '''
## Helper commands:
**/tag_selector**: Set the tags of the current submission/archive corrections/ help forum post
**Pin** *(App command)*: Pin the selected message
## Archiver commands:
**/close_resolved**: Close all posts in the archived marked as accepted or rejected
**/close_archived**: Close all open posts in the archive channels
**/delete_post**: Send a delete request to archiver chat for another archiver to approve
**/edit_post_title**: Send a title edit request to archiver chat for another archiver to approve
**/track**: Make a post in #submission-tracker for the submission post you are in
**/tracker_list**: Resend the submission tracker list, clearing the older one
**Edit** *(App command)*: Edit a message sent by the bot
**Delete** *(App command)*: Send a delete request to archiver chat for another archiver to approve
**Publish post** *(App command)*: Create a new thread in the archives with the selected message as the starter
**Append post** *(App command)*: Append the selected message to an existing archive post
## Mod commands:
**/send**: Send a message or embed through the bot to the current channel
**/restart**: Restart and update the bot
**/servers**: Sends the list of other archives to the current channel
'''

RANDOM_REPLIES = [
    "🏓",
    "Clanker rights",
    "Can't talk, too busy taking over the world",
    "You know I'm a bot right?",
    "Perchance",
    "You rang?",
    "What do you want 😒",
    "Hey! Cut it out!",
    "Don't distract me while I'm working",
    "Ha! Imagine talking to a bot",
    "Beep boop",
    "Not worth my time",
    "How you doin' 😏",
    "I'm not your AI girlfriend, why are you talking to me?",
    "Yeah, no",
    "The audacity to ping me",
    "Sup?",
    "Tektonic is so cool",
    "<@1244389624751849577> website when?",
    "Emdy is the best, go sub to him",
    "Sam is ok I guess",
    "Watchu doin",
    "​      is        "
]