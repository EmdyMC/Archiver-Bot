import discord

# Constants

HIGHER_ROLES = {1161821342514036776, 1162049503503863808} # Mod, Archiver
MODERATOR_ID = 1161821342514036776
ARCHIVER_ID = 1162049503503863808
LOG_CHANNEL = 1343664979831820368 # Bot-logs
NON_ARCHIVE_CATEGORIES = {1355756508394160229, 1358435852153258114, 1163087048173965402, 1378966923152195655, 1182932696662560798, 1374225342948053032, 1161803873317568583}
SUBMISSIONS_CHANNEL = 1161814713496256643
SUBMISSIONS_TRACKER_CHANNEL = 1394308822926889060
ARCHIVERS = {869534786094518302, 1170351112973467681, 247478244960501760, 301919226078298114, 697416598100770916, 619840922129268746, 443157310341251083, 549734176455262209, 549734176455262209, 709149578636689468, 828951132721774604, 744300374550118562, 697092662511272036, 513900971219353600, 640174975675793430, 900779759997419530, 394609623530995712, 330610358094004225}
RESOLVED_TAGS = {1183092798908534804, 1197302327065972776} # Rejected, Archived
GENERAL_RESOLVED_TAGS = {1183092798908534804, 1183092754834788414, 1197302327065972776, 1284913456033562736, 1285932035147300885, 1378041226019868702} # Rejected, Accepted, Archived, Solved, Rejected correction, Solved help
FORUMS = {1161814713496256643, 1284851559947305052, 1378037810975473846} # Submissions, Archive-corrections, Help-forum
TAG_COLOUR = {
    "Accepted": discord.Colour.green(),
    "Rejected": discord.Colour.red(),
    "Solved": discord.Colour.green(),
    "Archived": discord.Colour.dark_blue()} # Embed Colour based on tag
UPPER_TAGS = {"Accepted", "Rejected", "Solved", "Pending", "Archived"}
TESTING_EMOJI = "🧪"
CLOCK_EMOJI = "🕥"
CROSS_EMOJI = "❌"

# Embed text

OTHER_ARCHIVES = '''<:std:1399677131004580051> [**Storage Tech**](https://discord.gg/JufJ6uf) Item sorting and storage
<:slime:1399677082472153098> [**Slimestone Tech Archive**](https://discord.gg/QQX5RBaHzK) Flying machines and movable contraptions
<:mtdr:1399677041946923061> [**Minecraft Tech Discord Recollector**](https://discord.gg/UT8ns46As9) Index of TMC SMP and archive servers
<:tnt:1399677165104009226> [**TNT Archive**](https://discord.gg/vPyUBcdmZV) TNT cannon tech and projectile physics
<:tree:1399677175803805696> [**Tree Huggers**](https://discord.gg/8bUbuuS) Tree farm development
<:hfh:1399677019767312404> [**Huge Fungi Huggers**](https://discord.gg/EKKkyfcPPV) Nether tree and foliage farm development
<:cart:1399676987928219739> [**Cartchives**](https://discord.gg/8nGNTewveC) Piston bolts and minecart based tech
<:wither:1399677185870008330> [**Wither Archive**](https://discord.gg/Ea28MyKB3J) Wither tech archive and development 
<:sos:1399677094169940139> [**Saints of Suppression**](https://discord.gg/xa7QWAeAng) Light and update suppression and skipping
<:aca:1399676962464600155> [**Autocrafting Archive**](https://discord.gg/guZdbQ9KQe) Crafters and modded autocrafting table tech
<:comp:1399677007406698516> [**Computational Minecraft Archive**](https://discord.gg/jSe4jR5Kx7) TMC-oriented computational redstone logic
<:tmcra:1399677154702135328> [**TMC Resources Archive**](https://discord.gg/E4q8WDUc7k) Compilation of TMC tricks, links, and resources
<:luke:1399677029707808768> [**Luke's Video Archive**](https://discord.gg/KTDacw6JYk) Chinese (BiliBiili) tech recollector

<:ore:1399677056584781946> [**Open Redstone**](https://discord.gg/zjWRarN) (DiscOREd) Computational redstone community
<:squid:1399677105033183232> [**Piston Door Catalogue**](https://discord.gg/Khj8MyA) (Redstone Squid's Records Catalogue) Piston door index
<:ssf:1399677117884534875> [**Structureless Superflat Archive**](https://discord.gg/96Qm6e2AVH) (SSf Archive) Structureless superflat tech
<:rta:1399677071919288342> [**Russian Technical Minecraft Catalogue**](https://discord.com/invite/bMZYHnXnCA) (RTMC Каталог) Russian TMC archive
<:tba:1399677142660546620> [**Technical Bedrock Archive**](https://discord.com/invite/technical-bedrock-archive-715182000440475648) Bedrock TMC archive'''