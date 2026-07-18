import asyncio
import json
import time
import sys
import threading
from datetime import datetime, date, timedelta
from typing import List, Callable, Optional
import pytz
import httpx

from models.stocks import NIFTY50, SYMBOLS
import breeze_creds as config

IST = pytz.timezone("Asia/Kolkata")

# ── Hardcoded NSE stock tokens for Breeze ─────────────────────────────────────
# Format: "4.1!TOKEN" — 4=NSE, 1=exchange quotes
# These are permanent NSE instrument tokens, never change
STOCK_TOKENS = {
    "RELIANCE":   "4.1!2885",   "HDFCBANK":   "4.1!1333",
    "ICICIBANK":  "4.1!4963",   "INFY":       "4.1!1594",
    "TCS":        "4.1!11536",  "BHARTIARTL": "4.1!10604",
    "SBIN":       "4.1!3045",   "ITC":        "4.1!1660",
    "LT":         "4.1!11483",  "AXISBANK":   "4.1!5900",
    "KOTAKBANK":  "4.1!1922",   "HINDUNILVR": "4.1!1394",
    "ASIANPAINT": "4.1!236",    "MARUTI":     "4.1!10999",
    "BAJFINANCE": "4.1!317",    "WIPRO":      "4.1!3787",
    "HCLTECH":    "4.1!7229",   "TITAN":      "4.1!3506",
    "ULTRACEMCO": "4.1!2952",   "NESTLEIND":  "4.1!17963",
    "POWERGRID":  "4.1!14977",  "NTPC":       "4.1!11630",
    "ONGC":       "4.1!2475",   "JSWSTEEL":   "4.1!11723",
    "TATAMOTORS": "4.1!3456",   "TATASTEEL":  "4.1!3505",
    "HINDALCO":   "4.1!1363",   "COALINDIA":  "4.1!20374",
    "BAJAJFINSV": "4.1!16675",  "ADANIENT":   "4.1!25",
    "ADANIPORTS": "4.1!15083",  "CIPLA":      "4.1!694",
    "DRREDDY":    "4.1!881",    "SUNPHARMA":  "4.1!3351",
    "APOLLOHOSP": "4.1!157",    "DIVISLAB":   "4.1!10940",
    "EICHERMOT":  "4.1!910",    "HEROMOTOCO": "4.1!1348",
    "BAJAJ_AUTO": "4.1!16669",  "M_M":        "4.1!2031",
    "TECHM":      "4.1!13538",  "HDFCLIFE":   "4.1!467",
    "SBILIFE":    "4.1!21808",  "GRASIM":     "4.1!1232",
    "INDUSINDBK": "4.1!5258",   "TATACONSUM": "4.1!3432",
    "BRITANNIA":  "4.1!547",    "BPCL":       "4.1!526",
    "SHRIRAMFIN": "4.1!3721",   "VEDL":       "4.1!3063",
}

# Reverse map: token → symbol
TOKEN_TO_SYM = {v: k for k, v in STOCK_TOKENS.items()}

# Breeze NSE stock code mapping
# Key = our symbol, Value = Breeze stock_code in their CSV
BREEZE_CODES = {
    # Nifty 50 — verified from Breeze CSV
    "RELIANCE":   "RELIND",  "HDFCBANK":   "HDFBAN",  "ICICIBANK":  "ICICIB",
    "INFY":       "INFTEC",  "TCS":        "TCS",     "BHARTIARTL": "BHAAIR",
    "SBIN":       "STABAN",  "ITC":        "ITC",     "LT":         "LARTOU",
    "AXISBANK":   "AXIBAN",  "KOTAKBANK":  "KOTMAH",  "HINDUNILVR": "HINLEV",
    "ASIANPAINT": "ASIPAI",  "MARUTI":     "MARUTI",  "BAJFINANCE": "BAJFI",
    "WIPRO":      "WIPRO",   "HCLTECH":    "HCLTEC",  "TITAN":      "TITIND",
    "ULTRACEMCO": "ULTCEM",  "NESTLEIND":  "NESIND",  "POWERGRID":  "POWGRI",
    "NTPC":       "NTPC",    "ONGC":       "ONGC",    "JSWSTEEL":   "JSWSTE",
    "TATAMOTORS": "TATCOV",  "TATASTEEL":  "TATSTE",  "HINDALCO":   "HINDAL",
    "COALINDIA":  "COALIN",  "BAJAJFINSV": "BAFINS",  "ADANIENT":   "ADAENT",
    "ADANIPORTS": "ADAPOR",  "CIPLA":      "CIPLA",   "DRREDDY":    "DRREDD",
    "SUNPHARMA":  "SUNPHA",  "APOLLOHOSP": "APOHOS",  "DIVISLAB":   "DIVLAB",
    "EICHERMOT":  "EICMOT",  "HEROMOTOCO": "HERHON",  "BAJAJ-AUTO": "BAAUTO",
    "M&M":        "MAHMAH",  "TECHM":      "TECMAH",  "HDFCLIFE":   "HDFSTA",
    "SBILIFE":    "SBILIF",  "GRASIM":     "GRASIM",  "INDUSINDBK": "INDBA",
    "TATACONSUM": "TATGLO",  "BRITANNIA":  "BRIIND",  "BPCL":       "BHAPET",
    "SHRIRAMFIN": "SHRTRA",  "VEDL":       "VEDLIM",
    # Nifty Next 50 / Midcap — verified
    "ADANIGREEN": "ADAGRE",  "ADANIPOWER": "ADAPOW",  "ATGL":       "ADAGAS",
    "AWL":        "ADAWIL",  "AMBUJACEM":  "AMBCE",   "BAJAJHLDNG": "BAJHOL",
    "BANKBARODA": "BANBAR",  "BERGEPAINT": "BERPAI",  "BEL":        "BHAELE",
    "BHEL":       "BHEL",    "BOSCHLTD":   "BOSLIM",  "CANBK":      "CANBAN",
    "CHOLAFIN":   "CHOINV",  "COLPAL":     "COLPAL",  "DLF":        "DLFLIM",
    "DABUR":      "DABIND",  "GODREJCP":   "GODCON",  "HAVELLS":    "HAVIND",
    "ICICIGI":    "ICILOM",  "ICICIPRULI": "ICIPRU",  "IOC":        "INDOIL",
    "IRCTC":      "INDRAI",  "JINDALSTEL": "JINPOW",  "LTIM":       "LTINFO",
    "LTTS":       "LTTEC",   "LUPIN":      "LUPIN",   "MUTHOOTFIN": "MUTFIN",
    "NAUKRI":     "INFEDG",  "NMDC":       "NATMIN",  "OFSS":       "ORAFIN",
    "PAGEIND":    "PAGIND",  "PIDILITIND": "PIDIND",  "PIIND":      "PIIND",
    "PNB":        "PUNBAN",  "RECLTD":     "RURELE",  "SAIL":       "SAIL",
    "SIEMENS":    "SIEMEN",  "SRF":        "SRF",     "TATAPOWER":  "TATPOW",
    "TORNTPHARM": "TORPHA",  "TRENT":      "TRENT",   "UBL":        "UNIBR",
    "UNIONBANK":  "UNIBAN",  "UPL":        "UNIP",    "VBL":        "VARBEV",
    "ZOMATO":     "ZOMLIM",  "ZYDUSLIFE":  "CADHEA",
    # Midcap / Smallcap — verified
    "ABCAPITAL":  "ADICAP",  "ABFRL":      "ADIFAS",  "APLAPOLLO":  "APLAPO",
    "AUBANK":     "AUSMA",   "AUROPHARMA": "AURPHA",  "BALKRISIND": "BALIND",
    "BANDHANBNK": "BANBAN",  "BATAINDIA":  "BATIND",  "BHARATFORG": "BHAFOR",
    "BIOCON":     "BIOCON",  "COFORGE":    "NIITEC",  "CONCOR":     "CONCOR",
    "CUMMINSIND": "CUMIND",  "DALBHARAT":  "DALBHA",  "DEEPAKNTR":  "DEENIT",
    "FEDERALBNK": "FEDBAN",  "GODREJPROP": "GODPRO",  "HAL":        "HINAER",
    "HINDPETRO":  "HINPET",  "IDFCFIRSTB": "IDFBAN",  "IEX":        "INDEN",
    "INDHOTEL":   "INDHOT",  "INDIANB":    "INDIBA",  "IREDA":      "IREDA",
    "IRFC":       "INDR",    "JKCEMENT":   "JKCEME",  "JUBLFOOD":   "JUBFOO",
    "KALYANKJIL": "KALJEW",  "KPITTECH":   "KPITE",   "LALPATHLAB": "DRLAL",
    "LAURUSLABS": "LAULAB",  "LICHSGFIN":  "LICHF",   "MARICO":     "MARLIM",
    "MAXHEALTH":  "MAXHEA",  "MCX":        "MULCOM",  "MFSL":       "MAXFIN",
    "MOTHERSON":  "MOTSUM",  "NATIONALUM": "NATALU",  "NYKAA":      "FSNECO",
    "OBEROIRLTY": "OBEREA",  "PERSISTENT": "PERSYS",  "PETRONET":   "PETLNG",
    "POLYCAB":    "POLI",    "PRESTIGE":   "PREEST",  "PVRINOX":    "PVRLIM",
    "RBLBANK":    "RBLBAN",  "SBICARD":    "SBICAR",  "STARHEALTH": "STAHEA",
    "SUNDARMFIN": "SUNFIN",  "SUNDRMFAST": "SUNFAS",  "SUPREMEIND": "SUPIND",
    "SYNGENE":    "SYNINT",  "TATAELXSI":  "TATELX",  "TATATECH":   "TATTEC",
    "TIINDIA":    "TUBIN",   "TORNTPOWER": "TORPOW",  "TVSMOTOR":   "TVSMOT",
    "VGUARD":     "VGUARD",  "VOLTAS":     "VOLTAS",  "ZEEL":       "ZEEENT",
    "CGPOWER":    "CROGRE",  "SHYAMMETL":  "SHYMET",  "SONACOMS":   "SONBLW",
    # More midcap verified
    "JINDALSTEL": "JINSTE",  "CROMPTON":   "CROGR",   "EMAMILTD":   "EMALIM",
    "ESCORTS":    "ESCORT",  "EXIDEIND":   "EXIIND",  "GMRINFRA":   "GMRINF",
    "GRANULES":   "GRANUL",  "GUJGASLTD":  "GUJGAS",  "HFCL":       "HIMFUT",
    "INDUSTOWER": "BHAINF",
    "INOXWIND":   "INOWIN",  "IREDA":      "INDREN",  "JSL":        "JINSTA",
    "LTFOODS":    "LTOVER",  "METROPOLIS": "METHEA",  "MSUMI":      "MOTSU",
    "OBL":        "ORIBEL",  "PATANJALI":  "RUCSOY",  "PAYTM":      "ONE97",
    "PPLPHARMA":  "PIRPHA",  "RAMCOCEM":   "RAMCEM",
    "REDINGTON":  "REDIND",  "SCHAEFFLER": "FAGBEA",  "SKFINDIA":   "SKFIND",
    "SOLARINDS":  "SOLIN",   "SUMICHEM":   "SUMCH",   "TATACHEM":   "TATCHE",
    "TIMKEN":     "TIMIND",  "UCOBANK":    "UCOBAN",  "UNITDSPR":   "UNISPI",
    "WOCKPHARMA": "WOCKHA",  "AAVAS":      "AAVFIN",  "ABSLAMC":    "ADIAMC",
    "ACCELYA":    "ACCKAL",  "AEGISLOG":   "AEGLOG",  "AJANTPHARM": "AJAPHA",
    "ALKEM":      "ALKLAB",  "AMARAJABAT": "AMARAJ",  "AMBER":      "AMBEN",
    "APARINDS":   "APAIND",  "APTUS":      "APTVAL",  "ARVINDFASN": "ARVFAS",
    "ASTRAL":     "ASTPOL",  "BLUESTARCO": "BLUSTA",  "BRIGADE":    "BRIENT",
    "CAMPUS":     "CAMACT",  "CANFINHOME": "CANHOM",  "CARBORUNIV": "CARUNI",
    "CERA":       "CERSAN",  "CLEAN":      "CLESCI",  "CRAFTSMAN":  "CRAAUT",
    "DATAMATICS": "DATGLO",  "DCMSHRIRAM": "DCMSHR",  "DELHIVERY":  "DELLIM",
    "DEVYANI":    "DEVIN",   "JINDALSTEL": "JINDAD",
    "DIXON":      "DIXTEC",  "DOLLAR":     "DOLIN",   "EIDPARRY":   "EIDPAR",
    "ELGIEQUIP":  "ELGEQU",  "EPIGRAL":    "MEGF",    "EQUITASBNK": "EQUSMA",
    "ESABINDIA":  "ESAIND",  "ETHOSLTD":   "ETHLIM",  "FINEORG":    "FINORG",
    "GARFIBRES":  "GARWAL",  "GESHIP":     "GESHIP",  "GILLETTE":   "GILIND",
    "GLENMARK":   "GLEPHA",  "GNFC":       "GNFC",    "GODREJIND":  "GODIND",
    "HAPPSTMNDS": "HAPFOR",  "HOMEFIRST":  "HOMFIR",  "IPCALAB":    "IPCLAB",
    "JBCHEPHARM": "JBCHEM",  "JKPAPER":    "JKPAP",   "JKTYRE":     "JKTYRE",
    "JSWENERGY":  "JSWENE",  "JUSTDIAL":   "JUSDIA",  "KAJARIACER": "KAJCER",
    "KFINTECH":   "KFITEC",  "KRBL":       "KRBL",    "LALPATHLAB": "DRLAL",
    "LEMONTREE":  "LEMTRE",  "LXCHEM":     "LAXORG",  "MAPMYINDIA": "CEINFO",
    "MAXHEALTH":  "MAXHEA",  "MCDOWELL-N": "UNISPI",  "MMFL":       "MAHFIN",
    "MRPL":       "MRPL",    "NATCOPHARM": "NATPHA",  "NOCIL":      "NOCIL",
    "NYKAA":      "FSNECO",  "OBEROIRLTY": "OBEREA",  "OLECTRA":    "GOLTEL",
    "ORIENTCEM":  "ORICEM",  "PHOENIXLTD": "PHOMIL",  "PNBHOUSING": "PNBHOU",
    "POLYMED":    "POLMED",  "PRINCEPIPE": "PRIPIP",  "PVRINOX":    "PVRLIM",
    "QUESS":      "QUECOR",  "RADICO":     "RADKHA",  "RAILVIKAS":  "RAIVIK",
    "RITES":      "RITLIM",  "ROSSARI":    "ROSBIO",  "ROUTE":      "ROUMOB",
    "SAFARI":     "SAFIND",  "SAREGAMA":   "SAREIN",  "SBICARD":    "SBICAR",
    "SENCO":      "SENGOL",  "SOBHA":      "SOBDEV",  "SPANDANA":   "SPASPH",
    "STLTECH":    "STETEC",  "SUBROS":     "SUBROS",  "SUDARSCHEM": "SUDCHE",
    "SUVEN":      "SUVPH",   "SWSOLAR":    "STEWIL",  "SYMPHONY":   "SYMLIM",
    "TANLA":      "TANSOL",  "TATAELXSI":  "TATELX",  "TEJASNET":   "TEJNET",
    "THYROCARE":  "THYTEC",  "TRENT":      "TRENT",   "TRITURBINE": "TRITUR",
    "TVSMOTOR":   "TVSMOT",  "UTIAMC":     "UTIAMC",  "VIPIND":     "VIPIND",
    "VINATIORGA": "VINORG",  "VSTIND":     "VSTIND",  "WELCORP":    "WELCOR",
    "WELSPUNLIV": "WELIND",  "WESTLIFE":   "WESDEV",  "WHIRLPOOL":  "WHIIND",
    "WONDERLA":   "WONHOL",  "ZENSARTECH": "ZENTE",
    "FMGOETZE":   "FEDGOE",  "GAEL":       "GUJAE",   "GALAXYSURF": "GALSUR",
    "GAYAPROJ":   "GAYPRO",  "GLOBUSSPR":  "GLOSPI",  "GPPL":       "GUJPPL",
    "GRINDWELL":  "GRINOR",  "HLEGLAS":    "SWIGLA",  "IBREALEST":  "IBREALEST",
    "HOMEFIRST":  "HOMFIR",  "HONAUT":     "HONAUT",  "INTELLECT":  "INTDES",
    "IONEXCHANG": "IONEXC",  "IPCALAB":    "IPCLAB",  "ISEC":       "ICISEC",
    "JBMA":       "JBMAUT",  "JKPAPER":    "JKPAP",   "JSWENERGY":  "JSWENE",
    "JUSTDIAL":   "JUSDIA",  "KAYNES":     "KAYTEC",  "KPITTECH":   "KPITE",
    "LATENTVIEW": "LATVIE",  "LAURUSLABS": "LAULAB",  "MAPMYINDIA": "CEINFO",
    "MFSL":       "MAXFIN",  "MINDACORP":  "MINCOR",  "MRPL":       "MRPL",
    "NATCOPHARM": "NATPHA",  "NESCO":      "NESCO",   "NOCIL":      "NOCIL",
    "OLECTRA":    "GOLTEL",  "ORIENTCEM":  "ORICEM",  "PHOENIXLTD": "PHOMIL",
    "PNBHOUSING": "PNBHOU",  "POLYMED":    "POLMED",  "PRINCEPIPE": "PRIPIP",
    "RADICO":     "RADKHA",  "RAILVIKAS":  "RAIVIK",  "RITES":      "RITLIM",
    "ROSSARI":    "ROSBIO",  "ROUTE":      "ROUMOB",  "SAFARI":     "SAFIND",
    "SAREGAMA":   "SAREIN",  "SENCO":      "SENGOL",  "SOBHA":      "SOBDEV",
    "SPANDANA":   "SPASPH",  "STLTECH":    "STETEC",  "SUBROS":     "SUBROS",
    "SUVEN":      "SUVPH",   "SWSOLAR":    "STEWIL",  "SYMPHONY":   "SYMLIM",
    "TANLA":      "TANSOL",  "TEJASNET":   "TEJNET",  "THYROCARE":  "THYTEC",
    "TRITURBINE": "TRITUR",  "UTIAMC":     "UTIAMC",  "VINATIORGA": "VINORG",
    "VSTIND":     "VSTIND",  "WELCORP":    "WELCOR",  "WESTLIFE":   "WESDEV",
    "WHIRLPOOL":  "WHIIND",
    "360ONE": "IIFWEA",
    "3MINDIA": "3MIND",
    "AADHARHFC": "AADHOS",
    "AARTIIND": "AARIND",
    "ABB": "ABB",
    "ABBOTINDIA": "ABBIND",
    "ABDL": "ALLBLE",
    "ACC": "ACC",
    "ACE": "ACTCON",
    "ACMESOLAR": "ACMSOL",
    "ADANIENSOL": "ADATRA",
    "AFFLE": "AFFIND",
    "AIIL": "AUTINV",
    "ANANDRATHI": "ANARAT",
    "ANANTRAJ": "ANARAJ",
    "ANGELONE": "ANGBRO",
    "ANTHEM": "ANTBIO",
    "APOLLOTYRE": "APOTYR",
    "ARE&M": "AMARAJ",
    "ASAHIINDIA": "ASAIND",
    "ASHOKLEY": "ASHLEY",
    "ASTERDM": "ASTDM",
    "ATHERENERG": "ATHENE",
    "BAJAJHFL": "BAJHOU",
    "BALRAMCHIN": "BALCHI",
    "BANKINDIA": "BANIND",
    "BAYERCROP": "BAYIND",
    "BBTC": "BOMBUR",
    "BDL": "BHADYN",
    "BELRISE": "BELLIM",
    "BHARTIHEXA": "BHAHEX",
    "BIKAJI": "BIKFOO",
    "BLS": "BLSINT",
    "BLUEDART": "BLUDAR",
    "BLUEJET": "BLUJET",
    "BSE": "BSE",
    "BSOFT": "KPITEC",
    "CAMS": "COMAGE",
    "CANHLIFE": "CANHSB",
    "CAPLIPOINT": "CAPPOI",
    "CARTRADE": "CARTEC",
    "CASTROLIND": "CASIND",
    "CCL": "CCLPRO",
    "CEATLTD": "CEAT",
    "CENTRALBK": "CENBAN",
    "CGCL": "CAPGLO",
    "CGPOWER": "CROGRE",
    "CHALET": "CHAHOT",
    "CHAMBLFERT": "CHAFER",
    "CHENNPETRO": "CHEPET",
    "CHOLAHLDNG": "TUBINV",
    "CIEINDIA": "MAHCIE",
    "COCHINSHIP": "COCSHI",
    "COHANCE": "SUVPH",
    "CONCORDBIO": "CONBIO",
    "COROMANDEL": "CORINT",
    "CREDITACC": "CREGRA",
    "CRISIL": "CRISIL",
    "CUB": "CITUNI",
    "CYIENT": "CYILIM",
    "DATAPATTNS": "DATPAT",
    "DEEPAKFERT": "DEEFER",
    "DMART": "AVESUP",
    "DOMS": "DOMIND",
    "ECLERX": "ECLSER",
    "EIHOTEL": "EIHLIM",
    "ELECON": "ELEENG",
    "EMCURE": "EMCPHA",
    "EMMVEE": "EMMPHO",
    "ENDURANCE": "ENDTEC",
    "ENGINERSIN": "ENGIND",
    "ENRIN": "SIEENE",
    "ERIS": "ERILIF",
    "ETERNAL": "ZOMLIM",
    "FACT": "FACT",
    "FINCABLES": "FINCAB",
    "FIRSTCRY": "BRASOL",
    "FIVESTAR": "FIVSTA",
    "FLUOROCHEM": "GUJFLU",
    "FORCEMOT": "FORMOT",
    "FORTIS": "FORHEA",
    "FSL": "FIRSOU",
    "GABRIEL": "GABIND",
    "GAIL": "GAIL",
    "GALLANTT": "GALMET",
    "GICRE": "GIC",
    "GLAND": "GLAPH",
    "GLAXO": "GLAPHA",
    "GMDCLTD": "GUJMI",
    "GMRAIRPORT": "GMRINF",
    "GODFRYPHLP": "GODPHI",
    "GODIGIT": "GODIGI",
    "GODREJIND": "GODIND",
    "GPIL": "GODPOW",
    "GRAPHITE": "CAREVE",
    "GRAVITA": "GRAVIN",
    "GROWW": "BILGAR",
    "GRSE": "GARREA",
    "HBLENGINE": "HBLPOW",
    "HDBFS": "HDBFIN",
    "HDFCAMC": "HDFAMC",
    "HEG": "HEG",
    "HEXT": "HEXTEC",
    "HINDCOPPER": "HINCOP",
    "HINDZINC": "HINZIN",
    "HONASA": "HONCON",
    "HSCL": "HIMCHE",
    "HYUNDAI": "HYUMOT",
    "ICICIAMC": "ICIAMC",
    "IDEA": "IDECEL",
    "IFCI": "IFCI",
    "IGIL": "INTGEM",
    "IIFL": "IIFHOL",
    "IKS": "INVKNO",
    "INDGN": "INDLTD",
    "INDIACEM": "INDCEM",
    "IOB": "INDOVE",
    "IRB": "IRBINF",
    "IRCON": "IRCINT",
    "ITCHOTELS": "ITCHOT",
    "ITI": "ITI",
    "JAINREC": "JAIRES",
    "JINDALSAW": "JINSAW",
    "JIOFIN": "JIOFIN",
    "JMFINANCIL": "JMFINA",
    "JPPOWER": "JAIPOW",
    "JSWCEMENT": "JSWCEM",
    "JSWINFRA": "JSWINF",
    "JUBLINGREA": "JUBING",
    "JUBLPHARMA": "JUBLIF",
    "JWL": "COMENG",
    "JYOTICNC": "JYOCNC",
    "KARURVYSYA": "KARVYS",
    "KEC": "KECIN",
    "KEI": "KEIIND",
    "KIMS": "KRIINS",
    "KIRLOSENG": "KIRENG",
    "KPIL": "KALPOW",
    "KPRMILL": "KPRMIL",
    "LICI": "LIC",
    "LINDEINDIA": "LININ",
    "LLOYDSME": "LLOMET",
    "LODHA": "MACDEV",
    "LTF": "LTFINA",
    "M&MFIN": "MAHFIN",
    "MAHABANK": "BANMAH",
    "MANAPPURAM": "MANAFI",
    "MANKIND": "MAPHA",
    "MAZDOCK": "MAZDOC",
    "MEDANTA": "GLOHEA",
    "MGL": "MAHGAS",
    "MMTC": "MINERA",
    "MOTILALOFS": "MOTOSW",
    "MPHASIS": "MPHLIM",
    "MRF": "MRFTYR",
    "NAM-INDIA": "RELNIP",
    "NAVA": "NAVBHA",
    "NAVINFLUOR": "NAVFLU",
    "NBCC": "NBCC",
    "NCC": "NAGCON",
    "NETWEB": "NETTEC",
    "NEULANDLAB": "NEULAB",
    "NEWGEN": "NEWSOF",
    "NH": "NARHRU",
    "NHPC": "NHPC",
    "NIVABUPA": "NIVBUP",
    "NLCINDIA": "NEYLIG",
    "NTPCGREEN": "NTPGRE",
    "NUVAMA": "NUVWEA",
    "NUVOCO": "NUVVIS",
    "OIL": "OILIND",
    "OLAELEC": "OLAELE",
    "PARADEEP": "PARPHO",
    "PCBL": "PHICAR",
    "PFC": "POWFIN",
    "PFIZER": "PFIZER",
    "PGEL": "PGELEC",
    "PINELABS": "PINLAB",
    "PIRAMALFIN": "PIRFIN",
    "POLICYBZR": "PBFINT",
    "POONAWALLA": "MAGFI",
    "PREMIERENE": "PREENR",
    "PTCIL": "PTCIN",
    "RAILTEL": "RAICOR",
    "RAINBOW": "RAICHI",
    "RHIM": "ORIREF",
    "RKFORGE": "RAMFOR",
    "RPOWER": "RELPOW",
    "RRKABEL": "RRKAB",
    "RVNL": "RAIVIK",
    "SAGILITY": "SAGINI",
    "SAILIFE": "SAILIF",
    "SAPPHIRE": "SAPFOO",
    "SARDAEN": "SARENE",
    "SBFC": "SBFFIN",
    "SCHNEIDER": "SCHELE",
    "SCI": "SCI",
    "SHREECEM": "SHRCEM",
    "SIGNATURE": "SIGI",
    "SJVN": "SJVLIM",
    "SONATSOFTW": "SONSOF",
    "SUNTV": "SUNTV",
    "SUZLON": "SUZENE",
    "SYRMA": "SYRTEC",
    "TARIL": "TRAREC",
    "TATACAP": "TATCAP",
    "TATACOMM": "TATCOM",
    "TBOTEK": "TBOTEK",
    "TECHNOE": "TECEEC",
    "TEGA": "TEGIND",
    "THELEELA": "SCHBAN",
    "THERMAX": "THERMA",
    "TITAGARH": "TITWAG",
    "UNOMINDA": "MININD",
    "USHAMART": "USHMA",
    "VIJAYA": "VIJDIA",
    "VMM": "VISMEG",
    "VTL": "VARTEX",
    "WAAREEENER": "WAAENE",
    "YESBANK": "YESBAN",
    "ZFCVINDIA": "WABIND",
    "ZYDUSWELL": "ZYDWEL",
    "IGL":        "INDGAS",  "INDIAMART":  "INDMAR",  "INDIGO":     "INTAVI",
    "INGERRAND":  "INGRAN",  "KAMDHENU":   "KAMLIM",  "KANSAINER":  "KANNER",
    "KENNAMET":   "KENIN",   "KSCL":       "KAVSEE",  "LALPATHLAB": "DRLAL",
    "LEMONTREE":  "LEMTRE",  "LUXIND":     "LUXIND",  "MAHELEK":    "MAHELE",
    "MAHINDCIE":  "MAHCIE",  "MASFIN":     "MASFIN",  "MCDOWELL-N": "UNISPI",
    "MMFL":       "MAHFIN",  "MOLD-TEK":   "MOLPAC",  "MRSL":       "MRPL",
    "NAUKRI":     "INFEDG",  "NESCO":      "NESCO",   "NYLAA":      "FSNECO",
    "OLECTRA":    "GOLTEL",  "PGHH":       "PROGAM",  "PIIND":      "PIIND",
    "POLYMED":    "POLMED",  "QUESS":      "QUECOR",  "RPSGVENT":   "CESVEN",
    "SCHAEFFLER": "FAGBEA",  "SKFINDIA":   "SKFIND",  "SOLARINDS":  "SOLIN",
    "SUMICHEM":   "SUMCH",   "TATACHEM":   "TATCHE",  "TIMKEN":     "TIMIND",
    "UCOBANK":    "UCOBAN",  "UNITDSPR":   "UNISPI",  "WOCKPHARMA": "WOCKHA",
    "KNR":        "KNRCON",  "MIDHANI":    "MISDHA",  "NETWORK18":  "NETW18",
    "NIACL":      "NEWIN",   "NSLNISP":    "NMDSTE",  "PRSMJOHNSN": "PRICE",
    "PSPPROJECT":  "PSPPRO",  "QUESSCO":   "QUECOR",  "RPSGVENT":   "CESVEN",
    "SBICARD":    "SBICAR",  "STARHEALTH": "STAHEA",  "SUNDRMFAST": "SUNFAS",
    "SUPREMEIND": "SUPIND",  "SYNGENE":    "SYNINT",  "TATATECH":   "TATTEC",
    "TIINDIA":    "TUBIN",   "TORNTPOWER": "TORPOW",  "VGUARD":     "VGUARD",
    "ZEEL":       "ZEEENT",
    "RAJRATAN":   "RAJWIR",  "RALLIS":     "RALIND",  "RAYMOND":    "RAYMON",
    "SPARC":      "SUNADV",  "SPORTKING":  "SPOIND",  "STYLAMIND":  "STYABS",
    "SUPRIYA":    "SUPLIF",  "TASTYBITE":  "TASBIT",  "TATAINVEST": "TATINV",
    "TIMESCAN":   "TIMTEC",  "TIMETECHNO": "TIMTEC",  "TRIDENT":    "TRILTD",
    "TVSMOTOR":   "TVSMOT",  "UNITDSPR":   "UNISPI",  "VSTIND":     "VSTIND",
    "WELSPUNLIV": "WELIND",  "WOCKPHARMA": "WOCKHA",  "XPROINDIA":  "XPRIND",
    "YATHARTH":   "YATHOS",  "ZENTEC":     "ZENTEC",
    "TIPSINDLTD": "TIPFIL",  "UNIPARTS":   "UNIND",
}

_tick_callback: Optional[Callable] = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_connected = False
_breeze = None

def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    total_mins = now.hour * 60 + now.minute
    return 555 <= total_mins <= 930

def set_tick_callback(cb: Callable):
    global _tick_callback
    _tick_callback = cb

def set_event_loop(loop: asyncio.AbstractEventLoop):
    global _loop
    _loop = loop

def save_session(token: str):
    with open("session.json", "w") as f:
        json.dump({"session": token, "date": date.today().isoformat()}, f)
    config.BREEZE_SESSION = token
    print(f"✅ Session saved")

def load_session() -> Optional[str]:
    try:
        with open("session.json") as f:
            d = json.load(f)
        if d.get("date") == date.today().isoformat():
            return d.get("session")
    except Exception:
        pass
    return None

def is_connected() -> bool:
    return _connected

async def connect_breeze(session: str) -> bool:
    global _breeze, _connected
    save_session(session)
    try:
        import types
        fake_cfg = types.ModuleType("breeze_connect.config")
        fake_cfg.SECURITY_MASTER_URL   = "https://traderweb.icicidirect.com/Content/File/txtFile/ScripFile/StockScriptNew.zip"
        fake_cfg.API_URL               = "https://api.icicidirect.com/breezeapi/api/v1/"
        fake_cfg.BREEZE_NEW_URL        = "https://breezeapi.icicidirect.com/api/v2/"
        fake_cfg.LIVE_STREAM_URL       = "https://livestream.icicidirect.com"
        fake_cfg.LIVE_OHLC_STREAM_URL  = "https://breezeapi.icicidirect.com"
        fake_cfg.LIVE_FEEDS_URL        = "https://livefeeds.icicidirect.com"
        fake_cfg.STOCK_SCRIPT_CSV_URL  = "https://traderweb.icicidirect.com/Content/File/txtFile/ScripFile/StockScriptNew.zip"
        # Required enums/maps
        from enum import Enum
        class APIEndPoint(Enum):
            CUST_DETAILS = "customerdetails"
            HIST_CHART   = "historicalcharts"
            DEMAT_HOLDING = "dematholdings"
            FUND         = "funds"
            MARGIN       = "margin"
            ORDER        = "order"
            PORTFOLIO_HOLDING = "portfolioholdings"
            PORTFOLIO_POSITION = "portfoliopositions"
            QUOTE        = "quotes"
            OPT_CHAIN    = "optionchain"
            SQUARE_OFF   = "squareoff"
            TRADE        = "trades"
            LIMIT_CALCULATOR = "limitcalculator"
            MARGIN_CALULATOR = "margincalculator"
        class ResponseMessage(Enum):
            RATE_REFRESH_NOT_CONNECTED   = "Rate refresh not connected"
            RATE_REFRESH_DISCONNECTED    = "Rate refresh disconnected"
            OHLCV_STREAM_NOT_CONNECTED   = "OHLCV stream not connected"
            OHLCV_STREAM_DISCONNECTED    = "OHLCV stream disconnected"
            ORDER_REFRESH_NOT_CONNECTED  = "Order refresh not connected"
            ORDER_REFRESH_DISCONNECTED   = "Order refresh disconnected"
            STOCK_SUBSCRIBE_MESSAGE      = "{} subscribed successfully"
            STOCK_UNSUBSCRIBE_MESSAGE    = "{} unsubscribed successfully"
            ORDER_NOTIFICATION_SUBSRIBED = "Order notification subscribed"
            STRATEGY_STREAM_SUBSCRIBED   = "Strategy stream subscribed for {}"
            STRATEGY_STREAM_UNSUBSCRIBED = "Strategy stream unsubscribed for {}"
            STRATEGY_STREAM_NOT_CONNECTED = "Strategy stream not connected"
            API_SESSION_ERROR            = "API session error"
            BLANK_TRANSACTION_TYPE       = "Transaction type cannot be blank"
            BLANK_AMOUNT                 = "Amount cannot be blank"
            BLANK_SEGMENT                = "Segment cannot be blank"
            TRANSACTION_TYPE_ERROR       = "Transaction type error"
            ZERO_AMOUNT_ERROR            = "Amount cannot be zero"
            AMOUNT_DIGIT_ERROR           = "Amount must be digit"
            BLANK_EXCHANGE_CODE          = "Exchange code cannot be blank"
            EXCHANGE_CODE_ERROR          = "Exchange code error"
            BLANK_STOCK_CODE             = "Stock code cannot be blank"
            BLANK_FROM_DATE              = "From date cannot be blank"
            BLANK_TO_DATE                = "To date cannot be blank"
            INTERVAL_TYPE_ERROR          = "Interval type error"
            BLANK_INTERVAL               = "Interval cannot be blank"
            INTERVAL_TYPE_ERROR_HIST_V2  = "Interval type error for historical v2"
            EXCHANGE_CODE_HIST_V2_ERROR  = "Exchange code error for historical v2"
            BLANK_PRODUCT_TYPE_HIST_V2   = "Product type cannot be blank"
            PRODUCT_TYPE_ERROR_HIST_V2   = "Product type error for historical v2"
            BLANK_STRIKE_PRICE           = "Strike price cannot be blank"
            BLANK_EXPIRY_DATE            = "Expiry date cannot be blank"
            BLANK_PRODUCT_TYPE_NFO_BFO   = "Product type cannot be blank for NFO/BFO"
            PRODUCT_TYPE_ERROR_NFO_BFO   = "Product type error for NFO/BFO"
            BLANK_PRODUCT_TYPE           = "Product type cannot be blank"
            PRODUCT_TYPE_ERROR           = "Product type error"
            BLANK_ACTION                 = "Action cannot be blank"
            ACTION_TYPE_ERROR            = "Action type error"
            BLANK_ORDER_TYPE             = "Order type cannot be blank"
            ORDER_TYPE_ERROR             = "Order type error"
            BLANK_VALIDITY               = "Validity cannot be blank"
            VALIDITY_TYPE_ERROR          = "Validity type error"
            BLANK_QUANTITY               = "Quantity cannot be blank"
            BLANK_ORDER_ID               = "Order ID cannot be blank"
            RIGHT_TYPE_ERROR             = "Right type error"
            BLANK_LOTS                   = "Lots cannot be blank"
            CURRENCY_NOT_ALLOWED         = "Currency not allowed"
            NFO_FIELDS_MISSING_ERROR     = "NFO fields missing"
            BLANK_RIGHT_STRIKE_PRICE     = "Right and strike price cannot be blank"
            BLANK_RIGHT_EXPIRY_DATE      = "Right and expiry date cannot be blank"
            BLANK_EXPIRY_DATE_STRIKE_PRICE = "Expiry date and strike price cannot be blank"
            OPT_CHAIN_EXCH_CODE_ERROR    = "Option chain exchange code error"
            UNDER_LYING_ERROR            = "Underlying error"
            ORDER_FLOW                   = "Order flow error"
            STOP_LOSS_TRIGGER            = "Stop loss trigger error"
            OPTION_TYPE                  = "Option type error"
            SOURCE_FLAG                  = "Source flag error"
            MARKET_TYPE                  = "Market type error"
            FRESH_ORDER_LIMIT            = "Fresh order limit error"
        class ExceptionMessage(Enum):
            OHLC_SOCKET_CONNECTION_DISCONNECTED   = "OHLC socket disconnected"
            LIVESTREAM_SOCKET_CONNECTION_DISCONNECTED = "Live stream disconnected"
            ORDERNOTIFY_SOCKET_CONNECTION_DISCONNECTED = "Order notify disconnected"
            AUTHENICATION_EXCEPTION               = "Authentication failed"
            WRONG_EXCHANGE_CODE_EXCEPTION         = "Wrong exchange code"
            STOCK_NOT_EXIST_EXCEPTION             = "Stock {} does not exist for {}"
            EXCHANGE_CODE_EXCEPTION               = "Exchange code exception"
            STOCK_CODE_EXCEPTION                  = "Stock code exception"
            EXPIRY_DATE_EXCEPTION                 = "Expiry date exception"
            PRODUCT_TYPE_EXCEPTION                = "Product type exception"
            STRIKE_PRICE_EXCEPTION                = "Strike price exception"
            RIGHT_EXCEPTION                       = "Right exception"
            STOCK_INVALID_EXCEPTION               = "Stock invalid"
            SESSIONKEY_INCORRECT                  = "Session key incorrect"
            APPKEY_INCORRECT                      = "App key incorrect"
            SESSIONKEY_EXPIRED                    = "Session key expired"
            CUSTOMERDETAILS_API_EXCEPTION         = "Customer details API exception"
            API_REQUEST_EXCEPTION                 = "API request exception {} {}"
            ISEC_NSE_STOCK_MAP_EXCEPTION          = "ISEC NSE stock map exception"
            STREAM_OHLC_INTERVAL_ERROR            = "Stream OHLC interval error"
        class APIRequestType(Enum):
            GET    = "GET"
            POST   = "POST"
            PUT    = "PUT"
            DELETE = "DELETE"
        fake_cfg.APIEndPoint      = APIEndPoint
        fake_cfg.ResponseMessage  = ResponseMessage
        fake_cfg.ExceptionMessage = ExceptionMessage
        fake_cfg.APIRequestType   = APIRequestType
        fake_cfg.INTERVAL_TYPES   = ["1minute","5minute","30minute","1day","1second"]
        fake_cfg.INTERVAL_TYPES_HIST_V2 = ["1second","1minute","5minute","30minute","1hour","1day"]
        fake_cfg.INTERVAL_TYPES_STREAM_OHLC = ["1minute","5minute","30minute","1hour","1day"]
        fake_cfg.EXCHANGE_CODES_HIST   = ["nse","bse","nfo","ndx","mcx","bfo"]
        fake_cfg.EXCHANGE_CODES_HIST_V2 = ["nse","bse","nfo","ndx","mcx","bfo"]
        fake_cfg.FNO_EXCHANGE_TYPES    = ["nfo","ndx","mcx","bfo"]
        fake_cfg.PRODUCT_TYPES         = ["futures","options","cash","margin","eatm","mtf"]
        fake_cfg.PRODUCT_TYPES_HIST    = ["futures","options","cash"]
        fake_cfg.PRODUCT_TYPES_HIST_V2 = ["futures","options","cash"]
        fake_cfg.ACTION_TYPES          = ["buy","sell"]
        fake_cfg.ORDER_TYPES           = ["limit","market","stoploss"]
        fake_cfg.VALIDITY_TYPES        = ["day","ioc","vtc"]
        fake_cfg.RIGHT_TYPES           = ["call","put","others"]
        fake_cfg.TRANSACTION_TYPES     = ["debit","credit"]
        fake_cfg.STRATEGY_SUBSCRIPTION = []
        fake_cfg.channel_interval_map  = {"1minute":"1MinuteCandle","5minute":"5MinuteCandle","30minute":"30MinuteCandle","1hour":"1HourCandle","1day":"1DayCandle"}
        fake_cfg.feed_interval_map     = {"1MinuteCandle":"1minute","5MinuteCandle":"5minute","30MinuteCandle":"30minute","1HourCandle":"1hour","1DayCandle":"1day"}
        fake_cfg.TUX_TO_USER_MAP       = {"orderFlow":{},"limitMarketFlag":{},"orderType":{},"productType":{},"orderStatus":{},"optionType":{}}
        fake_cfg.ISEC_NSE_CODE_MAP_FILE = {}
        sys.modules["breeze_connect.config"] = fake_cfg
        if "breeze_connect.breeze_connect" in sys.modules:
            del sys.modules["breeze_connect.breeze_connect"]
        if "breeze_connect" in sys.modules:
            del sys.modules["breeze_connect"]

        from breeze_connect import BreezeConnect
        if _breeze is None:
            _breeze = BreezeConnect(api_key=config.BREEZE_API_KEY)

        loop = asyncio.get_event_loop()

        # Only generate session once per day
        session_file = "session_state.json"
        already_generated = False
        try:
            with open(session_file) as f:
                state = json.load(f)
            if state.get("date") == date.today().isoformat() and state.get("session") == session:
                already_generated = True
                print("✅ Reusing today's Breeze session")
        except Exception:
            pass

        # Always call generate_session to populate user_id and session_key
        # This does NOT invalidate the token — it just decodes the base64 session
        await loop.run_in_executor(
            None,
            lambda: _breeze.generate_session(
                api_secret=config.BREEZE_API_SECRET,
                session_token=session,
            )
        )
        if not already_generated:
            with open(session_file, "w") as f:
                json.dump({"date": date.today().isoformat(), "session": session}, f)
        print(f"✅ Breeze session generated — user_id: {_breeze.user_id}")

        def on_ticks(ticks):
            if not _tick_callback or not _loop:
                return
            try:
                asyncio.run_coroutine_threadsafe(_handle_ticks(ticks), _loop)
            except Exception:
                pass

        _breeze.on_ticks = on_ticks

        def ws_connect():
            try:
                print(f"🔌 Calling ws_connect()...")
                _breeze.ws_connect()
                print(f"✅ ws_connect() returned")
            except Exception as e:
                print(f"⚠ WS connect error detail: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()

        thread = threading.Thread(target=ws_connect, daemon=True)
        thread.start()
        await asyncio.sleep(3)
        print(f"🔍 user_id: {_breeze.user_id}")
        print(f"🔍 session_key: {_breeze.session_key}")
        print(f"🔍 handler connected: {_breeze.sio_rate_refresh_handler.sio.connected if _breeze.sio_rate_refresh_handler else None}")

        # Subscribe using hardcoded tokens — no get_names() needed
        # Mark as connected after session — subscription errors won't block this
        _connected = True
        print("✅ Breeze session active — historical data available")

        # Subscribe in background — errors here don't break anything
        asyncio.create_task(_subscribe_all_bg(loop))
        return True

    except Exception as e:
        print(f"⚠ Breeze connect error: {e}")
        _connected = False
        return False

async def _subscribe_all_bg(loop):
    """Subscribe in background — non-blocking."""
    await asyncio.sleep(2)
    await _subscribe_all(loop)

async def _subscribe_all(loop):
    """
    Subscribe to all stocks in NIFTY500 using tokens from
    Breeze stock script list loaded during generate_session().
    """
    from models.stocks import SYMBOLS, NIFTY50
    count = 0
    not_found = []

    if _breeze.stock_script_dict_list and len(_breeze.stock_script_dict_list) > 1:
        nse_dict = _breeze.stock_script_dict_list[1]
        print(f"🔍 Total NSE stocks in Breeze CSV: {len(nse_dict)}")
        # Search for remaining missing stocks
        # Debug JINDALSTEL specifically
        jind_keys = [k for k in nse_dict.keys() if 'JIND' in k.upper() or 'JSP' in k.upper() or 'JINDAL' in k.upper()][:10]
        print(f"🔍 JINDAL keys in CSV: {jind_keys}")
        missing3 = {
            'ICICIPRULI': ['ICIPRU','ICICPL','ICPRUL','PRUL','PRULI','ICICI P'],
            'IRCTC':      ['IRT','IRN','INDRAIL','INDRLY','RAILCOR'],
            'JINDALSTEL': ['JSP','JINSTE','JSPLTD','JIND','JSPOWER'],
            'LTIM':       ['LTI','LTIMIN','MINDTRE','LNTINFO','LNTTEC'],
            'MOTHERSON':  ['MOTHSUM','SAMSONS','SUMIWR','MOTSUM','MSSL'],
        }
        for sym, prefixes in missing3.items():
            found = None
            for p in prefixes:
                if p in nse_dict:
                    found = p
                    break
                matches = [k for k in nse_dict if k.startswith(p)]
                if matches:
                    found = matches[0]
                    break
            if found:
                print(f"  ✅ {sym} → '{found}'")
            else:
                # print all keys containing first 3 chars
                s = sym.replace('-','').replace('&','')[:3]
                all_m = [k for k in nse_dict if s.upper() in k.upper()][:8]
                print(f"  ❌ {sym} → all with '{s}': {all_m}")

    for sym in SYMBOLS:
        try:
            breeze_code = BREEZE_CODES.get(sym, sym)
            token = None

            if _breeze.stock_script_dict_list and len(_breeze.stock_script_dict_list) > 1:
                nse_dict = _breeze.stock_script_dict_list[1]
                # Try all variations
                for variant in [
                    breeze_code,
                    sym,
                    sym.replace("-", ""),
                    sym.replace("&", ""),
                    sym.replace("-AUTO", "AUTO"),
                    sym.replace("&M", "MM"),
                    sym.upper(),
                    breeze_code.upper(),
                ]:
                    token = nse_dict.get(variant)
                    if token:
                        break

            if token:
                stock_token = f"4.1!{token}"
                await loop.run_in_executor(
                    None,
                    lambda t=stock_token: _breeze.subscribe_feeds(stock_token=t)
                )
                TOKEN_TO_SYM[stock_token] = sym
                count += 1
            else:
                hardcoded = STOCK_TOKENS.get(sym)
                if hardcoded:
                    await loop.run_in_executor(
                        None,
                        lambda t=hardcoded: _breeze.subscribe_feeds(stock_token=t)
                    )
                    count += 1
                else:
                    not_found.append(sym)
            await asyncio.sleep(0.02)
        except Exception as e:
            pass

    print(f"✅ Subscribed to {count}/{len(SYMBOLS)} stocks")
    if not_found:
        print(f"⚠ No token found for: {not_found[:10]}{'...' if len(not_found) > 10 else ''}")

async def _handle_ticks(ticks):
    if not _tick_callback:
        return
    if not isinstance(ticks, list):
        ticks = [ticks]
    for tick in ticks:
        try:
            from models.stocks import NIFTY50
            # Breeze sends symbol as token "4.1!2885"
            raw_sym = tick.get("symbol", "")
            sym = TOKEN_TO_SYM.get(raw_sym)

            # Try stock_code field directly
            if not sym:
                stock_code = tick.get("stock_code", "")
                if stock_code in NIFTY50:
                    sym = stock_code
                else:
                    # Try reverse BREEZE_CODES lookup
                    for k, v in BREEZE_CODES.items():
                        if v == stock_code:
                            sym = k
                            break

            if not sym or sym not in NIFTY50:
                continue

            ltp    = float(tick.get("last",       tick.get("ltp",    0)) or 0)
            open_  = float(tick.get("open",                           0) or 0)
            high   = float(tick.get("high",                           0) or 0)
            low    = float(tick.get("low",                            0) or 0)
            volume = int(tick.get("ttq",          tick.get("volume",  0)) or 0)
            close  = float(tick.get("close",      NIFTY50[sym]["base"]) or NIFTY50[sym]["base"])

            if ltp <= 0:
                continue

            change    = round(ltp - close, 2)
            changepct = round((change / close) * 100, 2) if close > 0 else 0.0

            await _tick_callback(sym, {
                "ltp": ltp, "open": open_ or ltp,
                "high": high or ltp, "low": low or ltp,
                "volume": volume, "change": change,
                "change_percent": changepct,
            })
        except Exception:
            continue

async def disconnect():
    global _connected
    _connected = False
    if _breeze:
        try:
            _breeze.ws_disconnect()
        except Exception:
            pass

# ── Historical data ────────────────────────────────────────────────────────────
async def fetch_historical(sym: str, interval: str) -> List[dict]:
    """Yahoo fallback for any history needs."""
    return await _fetch_yahoo(sym, interval)

async def fetch_breeze_history(sym: str, interval: str) -> List[dict]:
    """Fetch real historical candles from Breeze REST API."""
    if not _breeze or not _connected:
        return []
    # Try Breeze code first, fallback to symbol directly
    code = BREEZE_CODES.get(sym, sym)
    result = await _fetch_breeze_history(code, interval)
    if not result and code != sym:
        # Try with raw symbol
        result = await _fetch_breeze_history(sym, interval)
    return result

async def _fetch_breeze_history(code: str, interval: str) -> List[dict]:
    try:
        loop    = asyncio.get_event_loop()
        now     = datetime.now(IST)
        from_dt, b_interval = _breeze_params(interval, now)
        data = await loop.run_in_executor(
            None,
            lambda: _breeze.get_historical_data_v2(
                interval=b_interval,
                from_date=from_dt.strftime("%Y-%m-%dT07:00:00.000Z"),
                to_date=now.strftime("%Y-%m-%dT07:00:00.000Z"),
                stock_code=code,
                exchange_code="NSE",
                product_type="cash",
            )
        )
        if not data:
            return []
        records = data.get("Success", []) or []
        candles = []
        for r in records:
            try:
                dt = r.get("datetime", "")
                t  = int(datetime.strptime(str(dt)[:19], "%Y-%m-%d %H:%M:%S")
                         .replace(tzinfo=IST).timestamp())
                o  = float(r.get("open",   0) or 0)
                h  = float(r.get("high",   0) or 0)
                l  = float(r.get("low",    0) or 0)
                c  = float(r.get("close",  0) or 0)
                v  = int(r.get("volume",   0) or 0)
                if o > 0 and c > 0 and t > 0 and _is_market_hours(t, interval):
                    candles.append({"time": t, "open": round(o, 2), "high": round(h, 2),
                                    "low": round(l, 2), "close": round(c, 2), "volume": v})
            except Exception:
                continue
        if candles:
            print(f"✅ Breeze history: {code} {interval} ({len(candles)} candles)")
        return sorted(candles, key=lambda x: x["time"])
    except Exception as e:
        print(f"⚠ Breeze history error {code}: {e}")
        return []

def _breeze_params(interval: str, now: datetime):
    # Breeze v2 accepted intervals: 1minute, 5minute, 30minute, 1hour, 1day
    MAP = {
        "1minute":  ("1minute",  timedelta(days=5)),
        "2minute":  ("1minute",  timedelta(days=5)),
        "3minute":  ("1minute",  timedelta(days=5)),
        "4minute":  ("1minute",  timedelta(days=5)),
        "5minute":  ("5minute",  timedelta(days=15)),
        "10minute": ("5minute",  timedelta(days=15)),
        "15minute": ("5minute",  timedelta(days=30)),
        "30minute": ("30minute", timedelta(days=30)),
        "1hour":    ("1hour",    timedelta(days=90)),
        "2hour":    ("1hour",    timedelta(days=90)),
        "4hour":    ("1hour",    timedelta(days=180)),
        "1day":     ("1day",     timedelta(days=365*2)),
        "1week":    ("1day",     timedelta(days=365*5)),
        "1month":   ("1day",     timedelta(days=365*10)),
        "1year":    ("1day",     timedelta(days=365*10)),
        "5year":    ("1day",     timedelta(days=365*10)),
    }
    b_interval, delta = MAP.get(interval, ("1day", timedelta(days=365)))
    return now - delta, b_interval

def _is_market_hours(timestamp: int, interval: str) -> bool:
    """Filter out pre-market and post-market candles for intraday timeframes."""
    # Only filter intraday intervals
    intraday = ["1minute","2minute","3minute","4minute","5minute",
                "10minute","15minute","30minute","1hour","2hour","4hour"]
    if interval not in intraday:
        return True
    try:
        dt = datetime.fromtimestamp(timestamp, tz=IST)
        total_mins = dt.hour * 60 + dt.minute
        # NSE market hours: 9:15 AM to 3:30 PM IST
        return 555 <= total_mins <= 930
    except Exception:
        return True

async def _fetch_yahoo(sym: str, interval: str) -> List[dict]:
    try:
        y_sym = sym.replace("_", "-").replace("&", "%26") + ".NS"
        MAP = {
            "1minute":  ("1m",  "1d"),  "2minute":  ("2m",  "5d"),
            "3minute":  ("1m",  "2d"),  "4minute":  ("2m",  "5d"),
            "5minute":  ("5m",  "5d"),  "10minute": ("5m",  "10d"),
            "15minute": ("15m", "1mo"), "30minute": ("30m", "1mo"),
            "1hour":    ("60m", "3mo"), "2hour":    ("60m", "6mo"),
            "4hour":    ("60m", "6mo"), "1day":     ("1d",  "2y"),
            "1week":    ("1wk", "5y"),  "1month":   ("1mo", "10y"),
            "1year":    ("1mo", "10y"), "5year":    ("1mo", "10y"),
        }
        yi, yr = MAP.get(interval, ("1d", "2y"))
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{y_sym}?interval={yi}&range={yr}"
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp  = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            data  = resp.json()
            r     = data.get("chart", {}).get("result", [{}])[0]
            times = r.get("timestamp", [])
            ohlcv = r.get("indicators", {}).get("quote", [{}])[0]
            candles = []
            for i, t in enumerate(times):
                o = ohlcv.get("open",   [None])[i]
                h = ohlcv.get("high",   [None])[i]
                l = ohlcv.get("low",    [None])[i]
                c = ohlcv.get("close",  [None])[i]
                v = ohlcv.get("volume", [None])[i]
                if o and h and l and c and t:
                    candles.append({"time": int(t), "open": round(float(o), 2),
                                    "high": round(float(h), 2), "low": round(float(l), 2),
                                    "close": round(float(c), 2), "volume": int(v or 0)})
            return sorted(candles, key=lambda x: x["time"])
    except Exception as e:
        print(f"⚠ Yahoo error {sym}: {e}")
        return []