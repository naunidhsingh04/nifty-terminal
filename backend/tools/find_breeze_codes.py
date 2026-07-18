"""
ISIN-based Breeze code finder - Fixed parser for NSEScripMaster.txt
Run from backend/tools/ folder.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import breeze_creds as config
from breeze_connect import BreezeConnect
import urllib.request, io, csv, zipfile

MISSING_STOCKS = {
    "360ONE": "INE466L01038", "3MINDIA": "INE470A01017", "AADHARHFC": "INE883F01010",
    "AARTIIND": "INE769A01020", "ABB": "INE117A01022", "ABBOTINDIA": "INE358A01014",
    "ABDL": "INE552Z01027", "ACC": "INE012A01025", "ACE": "INE731H01025",
    "ACMESOLAR": "INE622W01025", "ADANIENSOL": "INE931S01010", "AFFLE": "INE00WC01027",
    "AIIL": "INE206F01022", "ANANDRATHI": "INE463V01026", "ANANTRAJ": "INE242C01024",
    "ANGELONE": "INE732I01021", "ANTHEM": "INE0CZ201020", "APOLLOTYRE": "INE438A01022",
    "ARE&M": "INE885A01032", "ASAHIINDIA": "INE439A01020", "ASHOKLEY": "INE208A01029",
    "ASTERDM": "INE914M01019", "ATHERENERG": "INE0LEZ01016", "BAJAJHFL": "INE377Y01014",
    "BALRAMCHIN": "INE119A01028", "BANKINDIA": "INE084A01016", "BAYERCROP": "INE462A01022",
    "BBTC": "INE050A01025", "BDL": "INE171Z01026", "BELRISE": "INE894V01022",
    "BHARTIHEXA": "INE343G01021", "BIKAJI": "INE00E101023", "BLS": "INE153T01027",
    "BLUEDART": "INE233B01017", "BLUEJET": "INE0KBH01020", "BSE": "INE118H01025",
    "BSOFT": "INE836A01035", "CAMS": "INE596I01020", "CANHLIFE": "INE01TY01017",
    "CAPLIPOINT": "INE475E01026", "CARTRADE": "INE290S01011", "CASTROLIND": "INE172A01027",
    "CCL": "INE421D01022", "CEATLTD": "INE482A01020", "CENTRALBK": "INE483A01010",
    "CGCL": "INE180C01042", "CGPOWER": "INE067A01029", "CHALET": "INE427F01016",
    "CHAMBLFERT": "INE085A01013", "CHENNPETRO": "INE178A01016", "CHOLAHLDNG": "INE149A01033",
    "CIEINDIA": "INE536H01010", "COCHINSHIP": "INE704P01025", "COHANCE": "INE03QK01018",
    "CONCORDBIO": "INE338H01029", "COROMANDEL": "INE169A01031", "CREDITACC": "INE741K01010",
    "CRISIL": "INE007A01025", "CUB": "INE491A01021", "CYIENT": "INE136B01020",
    "DATAPATTNS": "INE0IX101010", "DEEPAKFERT": "INE501A01019", "DMART": "INE192R01011",
    "DOMS": "INE321T01012", "ECLERX": "INE738I01010", "EIHOTEL": "INE230A01023",
    "ELECON": "INE205B01031", "EMCURE": "INE168P01015", "EMMVEE": "INE1C6T01020",
    "ENDURANCE": "INE913H01037", "ENGINERSIN": "INE510A01028", "ENRIN": "INE1NPP01017",
    "ERIS": "INE406M01024", "ETERNAL": "INE758T01015", "FACT": "INE188A01015",
    "FINCABLES": "INE235A01022", "FIRSTCRY": "INE02RE01045", "FIVESTAR": "INE128S01021",
    "FLUOROCHEM": "INE09N301011", "FORCEMOT": "INE451A01017", "FORTIS": "INE061F01013",
    "FSL": "INE684F01012", "GABRIEL": "INE524A01029", "GAIL": "INE129A01019",
    "GALLANTT": "INE297H01019", "GICRE": "INE481Y01014", "GLAND": "INE068V01023",
    "GLAXO": "INE159A01016", "GMDCLTD": "INE131A01031", "GMRAIRPORT": "INE776C01039",
    "GODFRYPHLP": "INE260B01028", "GODIGIT": "INE03JT01014", "GODREJIND": "INE233A01035",
    "GPIL": "INE177H01039", "GRAPHITE": "INE371A01025", "GRAVITA": "INE024L01027",
    "GROWW": "INE0HOQ01053", "GRSE": "INE382Z01011", "HBLENGINE": "INE292B01021",
    "HDBFS": "INE756I01012", "HDFCAMC": "INE127D01025", "HEG": "INE545A01024",
    "HEXT": "INE093A01041", "HINDCOPPER": "INE531E01026", "HINDZINC": "INE267A01025",
    "HONASA": "INE0J5401028", "HSCL": "INE019C01026", "HYUNDAI": "INE0V6F01027",
    "ICICIAMC": "INE346A01027", "IDEA": "INE669E01016", "IFCI": "INE039A01010",
    "IGIL": "INE0Q9301021", "IIFL": "INE530B01024", "IKS": "INE115Q01022",
    "INDGN": "INE065X01017", "INDIACEM": "INE383A01012", "IOB": "INE565A01014",
    "IRB": "INE821I01022", "IRCON": "INE962Y01021", "ITCHOTELS": "INE379A01028",
    "ITI": "INE248A01017", "JAINREC": "INE0YD401026", "JINDALSAW": "INE324A01032",
    "JIOFIN": "INE758E01017", "JMFINANCIL": "INE780C01023", "JPPOWER": "INE351F01018",
    "JSWCEMENT": "INE718I01012", "JSWINFRA": "INE880J01026", "JUBLINGREA": "INE0BY001018",
    "JUBLPHARMA": "INE700A01033", "JWL": "INE209L01016", "JYOTICNC": "INE980O01024",
    "KARURVYSYA": "INE036D01028", "KEC": "INE389H01022", "KEI": "INE878B01027",
    "KIMS": "INE967H01025", "KIRLOSENG": "INE146L01010", "KPIL": "INE220B01022",
    "KPRMILL": "INE930H01031", "LICI": "INE0J1Y01017", "LINDEINDIA": "INE473A01011",
    "LLOYDSME": "INE281B01032", "LODHA": "INE670K01029", "LTF": "INE498L01015",
    "M&MFIN": "INE774D01024", "MAHABANK": "INE457A01014", "MANAPPURAM": "INE522D01027",
    "MANKIND": "INE634S01028", "MAZDOCK": "INE249Z01020", "MEDANTA": "INE474Q01031",
    "MGL": "INE002S01010", "MMTC": "INE123F01029", "MOTILALOFS": "INE338I01027",
    "MPHASIS": "INE356A01018", "MRF": "INE883A01011", "NAM-INDIA": "INE298J01013",
    "NAVA": "INE725A01030", "NAVINFLUOR": "INE048G01026", "NBCC": "INE095N01031",
    "NCC": "INE868B01028", "NETWEB": "INE0NT901020", "NEULANDLAB": "INE794A01010",
    "NEWGEN": "INE619B01017", "NH": "INE410P01011", "NHPC": "INE848E01016",
    "NIVABUPA": "INE995S01015", "NLCINDIA": "INE589A01014", "NTPCGREEN": "INE0ONG01011",
    "NUVAMA": "INE531F01023", "NUVOCO": "INE118D01016", "OIL": "INE274J01014",
    "OLAELEC": "INE0LXG01040", "PARADEEP": "INE088F01024", "PCBL": "INE602A01031",
    "PFC": "INE134E01011", "PFIZER": "INE182A01018", "PGEL": "INE457L01029",
    "PINELABS": "INE15B701018", "PIRAMALFIN": "INE202B01038", "POLICYBZR": "INE417T01026",
    "POONAWALLA": "INE511C01022", "PREMIERENE": "INE0BS701011", "PTCIL": "INE596F01018",
    "RAILTEL": "INE0DD101019", "RAINBOW": "INE961O01016", "RHIM": "INE743M01012",
    "RKFORGE": "INE399G01023", "RPOWER": "INE614G01033", "RRKABEL": "INE777K01022",
    "RVNL": "INE415G01027", "SAGILITY": "INE0W2G01015", "SAILIFE": "INE570L01029",
    "SAPPHIRE": "INE806T01020", "SARDAEN": "INE385C01021", "SBFC": "INE423Y01016",
    "SCHNEIDER": "INE839M01018", "SCI": "INE109A01011", "SHREECEM": "INE070A01015",
    "SIGNATURE": "INE903U01023", "SJVN": "INE002L01015", "SONATSOFTW": "INE269A01021",
    "SUNTV": "INE424H01027", "SUZLON": "INE040H01021", "SYRMA": "INE0DYJ01015",
    "TARIL": "INE763I01026", "TATACAP": "INE976I01016", "TATACOMM": "INE151A01013",
    "TBOTEK": "INE673O01025", "TECHNOE": "INE285K01026", "TEGA": "INE011K01018",
    "THELEELA": "INE0AQ201015", "THERMAX": "INE152A01029", "TITAGARH": "INE615H01020",
    "UNOMINDA": "INE405E01023", "USHAMART": "INE228A01035", "VIJAYA": "INE043W01024",
    "VMM": "INE01EA01019", "VTL": "INE825A01020", "WAAREEENER": "INE377N01017",
    "YESBANK": "INE528G01035", "ZFCVINDIA": "INE342J01019", "ZYDUSWELL": "INE768C01028",
}

def find_breeze_codes():
    print("🔌 Connecting to Breeze...")
    breeze = BreezeConnect(api_key=config.BREEZE_API_KEY)
    breeze.generate_session(
        api_secret=config.BREEZE_API_SECRET,
        session_token=config.BREEZE_SESSION
    )

    print("📥 Downloading SecurityMaster.zip...")
    url = "https://directlink.icicidirect.com/MotherAppMaster/SecurityMaster.zip"
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req, timeout=30)
    data = resp.read()
    print(f"   Downloaded {len(data):,} bytes")

    isin_to_code = {}

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        with z.open("NSEScripMaster.txt") as f:
            content = f.read().decode('utf-8', errors='ignore')

        reader = csv.reader(io.StringIO(content))
        headers = next(reader)
        # Strip spaces and quotes from headers
        headers = [h.strip().strip('"') for h in headers]
        print(f"   Columns: {headers[:12]}")

        # Find column indices
        isin_col  = headers.index("ISINCode")
        code_col  = headers.index("ShortName")
        series_col = headers.index("Series")

        print(f"   ISIN col: {isin_col}, Code col: {code_col}, Series col: {series_col}")

        count = 0
        for row in reader:
            if len(row) <= max(isin_col, code_col, series_col):
                continue
            isin   = row[isin_col].strip().strip('"')
            code   = row[code_col].strip().strip('"')
            series = row[series_col].strip().strip('"')
            # Only EQ series for equity stocks
            if isin.startswith("INE") and series == "EQ":
                isin_to_code[isin] = code
                count += 1

    print(f"   ✅ Mapped {count} NSE EQ stocks by ISIN")

    # Match against missing stocks
    found = {}
    not_found = {}

    for sym, isin in MISSING_STOCKS.items():
        if isin in isin_to_code:
            found[sym] = isin_to_code[isin]
        else:
            not_found[sym] = isin

    print(f"\n{'='*60}")
    print(f"✅ FOUND IN BREEZE ({len(found)} stocks):")
    print(f"{'='*60}")
    print("# Paste these into BREEZE_CODES in breeze_service.py:")
    for sym, code in sorted(found.items()):
        print(f'    "{sym}": "{code}",')

    print(f"\n{'='*60}")
    print(f"❌ NOT IN BREEZE ({len(not_found)} stocks):")
    print(f"{'='*60}")
    for sym, isin in sorted(not_found.items()):
        print(f"  {sym}: {isin}")

    return found, not_found

if __name__ == "__main__":
    find_breeze_codes()