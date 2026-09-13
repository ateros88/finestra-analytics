from datetime import datetime
import os
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from supabase import Client, create_client
import streamlit as st

# --- 0. Konfiguration & Supabase Anslutning ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(
    page_title="Finestra Analytics",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Dölj sidofältet helt och gör rubriker vita
st.markdown(
    """
    <style>
        [data-testid="stSidebarNav"] {display: none;}
        section[data-testid="stSidebar"] {width: 0px !important; display: none;}
        h1, h2, h3 {
            color: #FFFFFF !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# --- 1. Riktig Inloggningskontroll (Supabase Auth) ---
if "user" not in st.session_state:
  st.session_state["user"] = None

# Kolla om det finns en aktiv session
session = supabase.auth.get_session()
if session:
  st.session_state["user"] = session.user

# Om användaren INTE är inloggad: Visa inloggning/registrering för betatestare
if not st.session_state["user"]:
  st.markdown(
      "<h1 style='text-align: center;'>Finestra Analytics</h1>",
      unsafe_allow_html=True,
  )
  st.markdown(
      "<h3 style='text-align: center; color: gray;'>Betatest</h3>",
      unsafe_allow_html=True,
  )
  st.write("")

  col1, col2, col3 = st.columns([1, 2, 1])
  with col2:
    tab_login, tab_signup = st.tabs(["Logga in", "Skapa betakonto"])

    with tab_login:
      email = st.text_input("E-post", key="login_email")
      password = st.text_input("Lösenord", type="password", key="login_password")

      if st.button("Logga in", width="stretch"):
        try:
          res = supabase.auth.sign_in_with_password(
              {"email": email, "password": password}
          )
          st.session_state["user"] = res.user
          st.success("Inloggad!")
          st.rerun()
        except Exception as e:
          st.error(f"Inloggning misslyckades: {e}")

    with tab_signup:
      st.write("Skapa ett konto för att delta i betatestet.")
      new_email = st.text_input("E-post", key="signup_email")
      new_password = st.text_input(
          "Välj lösenord", type="password", key="signup_password"
      )

      if st.button("Registrera konto", width="stretch"):
        try:
          supabase.auth.sign_up({"email": new_email, "password": new_password})
          st.success("Konto skapat! Du kan nu logga in.")
        except Exception as e:
          st.error(f"Kunde inte registrera: {e}")

  # Stoppar resten av appen från att visas för oinloggade
  st.stop()

# --- 2. Initiera session_state för nivåer (när man är inloggad) ---
if "user_tier" not in st.session_state:
  st.session_state["user_tier"] = "insight"

# Definiera rättigheter
TIER_FEATURES = {
    "insight": ["top4_dashboard"],
    "advance": [
        "top4_dashboard",
        "full_dashboard",
        "sector_selection",
        "sector_rotation",
        "deep_analysis",
    ],
    "master": [
        "top4_dashboard",
        "full_dashboard",
        "sector_selection",
        "sector_rotation",
        "deep_analysis",
        "premium_blog",
    ],
}


def has_access(user_tier, feature):
  return feature in TIER_FEATURES.get(user_tier, ["top4_dashboard"])


@st.cache_data(ttl=600)
def hämta_data():
  try:
    response = supabase.table("analyser").select("*").execute()
    return pd.DataFrame(response.data)
  except:
    return pd.DataFrame()


# Mappning för svenska sektornamn
sektor_namn_sv = {
    "Technology": "Teknologi",
    "Financial Services": "Finans",
    "Healthcare": "Hälsovård",
    "Consumer Cyclical": "Konsument (Sällanköp)",
    "Consumer Defensive": "Konsument (Bas)",
    "Industrials": "Industri",
    "Energy": "Energi",
    "Utilities": "Kraftförsörjning",
    "Basic Materials": "Material",
    "Real Estate": "Fastigheter",
    "Communication Services": "Kommunikation",
}

# --- Hjälpfunktion för dynamisk valutaformatering ---
def formatera_pris(pris_varde, valuta_kod):
  valuta_symboler = {
      "USD": "$",
      "SEK": " kr",
      "NOK": " kr",
      "DKK": " DKK",
      "EUR": "€",
      "GBP": "£",
  }
  sym = valuta_symboler.get(str(valuta_kod).upper(), "$")
  pris_str = f"{float(pris_varde):.2f}"
  
  # Placera symbolen snyggt beroende på valuta
  if sym in ["$", "€", "£"]:
    return f"{sym}{pris_str}"
  else:
    return f"{pris_str}{sym}"

# --- 3. UI Layout ---
header_col1, header_col2 = st.columns([0.6, 0.4])

with header_col1:
  st.markdown(
      "<h1 style='color: black; margin-bottom: 0;'>Finestra Analytics</h1>",
      unsafe_allow_html=True,
  )

with header_col2:
  user_email = st.session_state["user"].email
  st.markdown(
      f"""
        <div style='display: flex; justify-content: flex-end; align-items: center; gap: 15px; padding-top: 15px;'>
            <span style='color: #555; font-size: 14px;'>Inloggad: <b>{user_email}</b></span>
        </div>
    """,
      unsafe_allow_html=True,
  )

  col_knapp1, col_knapp2 = st.columns([2, 1])
  with col_knapp2:
    if st.button("Logga ut", key="logout_btn"):
      supabase.auth.sign_out()
      st.session_state["user"] = None
      st.rerun()

st.divider()

tabs = st.tabs(
    ["DASHBOARD", "MARKET RESEARCH", "PRICING", "FAQ", "KONTO", "INSTÄLLNINGAR"]
)

# --- DASHBOARD ---
with tabs[0]:
  df = hämta_data()

  if not df.empty and "senast_uppdaterad" in df.columns:
    try:
      senaste_str = df["senast_uppdaterad"].dropna().max()
      if pd.notna(senaste_str):
        dt = datetime.fromisoformat(str(senaste_str).replace("Z", ""))
        senast_kopierad = dt.strftime("%Y-%m-%d %H:%M")
      else:
        senast_kopierad = "Okänd"
    except Exception:
      senast_kopierad = "Okänd"
  else:
    senast_kopierad = "Okänd"

  col_titel, col_tid = st.columns([3, 1])
  with col_titel:
    st.subheader("Marknadsläge")
  with col_tid:
    st.markdown(
        f"<p style='text-align: right; color: gray; font-size: 13px; margin-top:"
        f" 10px;'>Senast uppdaterad: <b>{senast_kopierad}</b></p>",
        unsafe_allow_html=True,
    )

  if not df.empty:
    df["potential"] = pd.to_numeric(
        df["potential"], errors="coerce"
    ).fillna(0)
    df["nuvarande"] = pd.to_numeric(
        df["nuvarande"], errors="coerce"
    ).fillna(0)
    df["target"] = pd.to_numeric(df["target"], errors="coerce").fillna(0)
    df["antal_koprek"] = pd.to_numeric(
        df["antal_koprek"], errors="coerce"
    ).fillna(0)

    # Om valuta-kolumn saknas i tabellen tillfälligt, sätt USD som standard
    if "valuta" not in df.columns:
      df["valuta"] = "USD"

    max_pot = df["potential"].max()
    norm_pot = (
        df["potential"] / (max_pot if max_pot > 0 else 1)
    ) * 60
    max_rek = df["antal_koprek"].max()
    norm_rek = (
        df["antal_koprek"] / (max_rek if max_rek > 0 else 1)
    ) * 40
    df["Finestra Score"] = (norm_pot + norm_rek).round(0)

    df["sektor_sv"] = df["sektor"].map(sektor_namn_sv).fillna(df["sektor"])

    # Applicera dynamisk valutaformatering
    df["Kurs"] = [formatera_pris(row["nuvarande"], row["valuta"]) for _, row in df.iterrows()]
    df["Riktkurs"] = [formatera_pris(row["target"], row["valuta"]) for _, row in df.iterrows()]
    df["Potential (%)"] = df["potential"].round(1).astype(str) + " %"

    display_df = df.rename(
        columns={
            "ticker": "Ticker",
            "name": "Namn",
            "sektor_sv": "Sektor",
            "antal_koprek": "Köprekar",
        }
    )

    if has_access(st.session_state["user_tier"], "sector_selection"):
      unika_sektorer = sorted(
          [s for s in df["sektor_sv"].unique() if s and s != "N/A"]
      )
      sektorer = ["Visa Alla (Topp 4)"] + unika_sektorer
      vald_sektor = st.selectbox("Välj sektor:", sektorer)

      if vald_sektor == "Visa Alla (Topp 4)":
        visnings_df = (
            display_df.sort_values(by="Finestra Score", ascending=False)
            .head(4)
        )
      else:
        visnings_df = display_df[
            display_df["Sektor"] == vald_sektor
        ].sort_values(by="Finestra Score", ascending=False)
    else:
      st.info("Visar Topp 4 (Insight). Uppgradera till Advance för sektorval!")
      visnings_df = (
          display_df.sort_values(by="Finestra Score", ascending=False).head(4)
      )

    st.dataframe(
        visnings_df[[
            "Ticker",
            "Namn",
            "Finestra Score",
            "Kurs",
            "Riktkurs",
            "Potential (%)",
            "Köprekar",
        ]],
        width=1000,
        hide_index=True,
    )

# --- MARKET RESEARCH ---
with tabs[1]:
    st.subheader("Market Research")
    st.write("### Sektorrotation (Historisk Utveckling)")

    sektor_namn = {
        "XLK": "Teknologi",
        "XLF": "Finans",
        "XLV": "Hälsovård",
        "XLY": "Konsument (Sällanköp)",
        "XLP": "Konsument (Bas)",
        "XLI": "Industri",
        "XLE": "Energi",
        "XLU": "Kraftförsörjning",
        "XLB": "Material",
        "XLRE": "Fastigheter",
    }

    if has_access(st.session_state["user_tier"], "sector_rotation"):
        tidsintervall = st.radio(
            "Välj tidsperiod:",
            ["1 vecka", "1 månad", "1 år", "3 år", "5 år"],
            horizontal=True,
            index=2,
            label_visibility="collapsed"
        )

        intervall_mapping = {
            "1 vecka": ("5d", "1d"),
            "1 månad": ("1mo", "1d"),
            "1 år": ("1y", "1d"),
            "3 år": ("3y", "1d"),
            "5 år": ("5y", "1d"),
        }

        period_str, interval_str = intervall_mapping[tidsintervall]

        @st.cache_data(ttl=3600)
        def hamta_live_sektor_historik(period, interval):
            data_list = []
            for ticker, namn in sektor_namn.items():
                try:
                    df = yf.download(
                        ticker, period=period, interval=interval, progress=False
                    )
                    if not df.empty:
                        if isinstance(df.columns, pd.MultiIndex):
                            df = df.droplevel(1, axis=1)
                        
                        if "Close" in df.columns:
                            df = df[["Close"]].reset_index()
                            df.columns = ["datum", "pris"]
                            df["ticker"] = ticker
                            df["sektor_namn"] = f"{namn} ({ticker})"

                            start_pris = df["pris"].iloc[0]
                            df["förändring"] = (
                                (df["pris"] - start_pris) / start_pris
                            ) * 100

                            data_list.append(df)
                except Exception as e:
                    print(f"Kunde inte hämta {ticker}: {e}")

            if data_list:
                return pd.concat(data_list, ignore_index=True)
            return pd.DataFrame()

        df_sektor = hamta_live_sektor_historik(period_str, interval_str)

        if not df_sektor.empty:
            fig = px.line(
                df_sektor,
                x="datum",
                y="förändring",
                color="sektor_namn",
                labels={
                    "förändring": "Avkastning (%)",
                    "datum": "Datum",
                    "sektor_namn": "Sektor",
                },
                template="plotly_dark",
            )

            fig.update_layout(
                hovermode="x unified",
                yaxis_ticksuffix=" %",
                xaxis_title="",
                yaxis_title="Avkastning (%)",
                plot_bgcolor="#0A1118",
                paper_bgcolor="#0A1118",
                font=dict(color="#FFFFFF"),
            )
            fig.update_xaxes(tickformat="%Y-%m-%d")

            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                f"Grafen visar procentuell utveckling över vald period ({tidsintervall}). Datan är baserad på amerikanska SPDR Sector ETFs."
            )

            st.write(f"#### Aktuell status ({tidsintervall})")
            senaste_per_ticker = (
                df_sektor.groupby("ticker")["datum"].max().reset_index()
            )
            df_senaste = pd.merge(senaste_per_ticker, df_sektor, on=["ticker", "datum"])
            df_senaste = df_senaste[["sektor_namn", "förändring"]].sort_values(
                by="förändring", ascending=False
            )
            df_senaste["förändring"] = (
                df_senaste["förändring"].round(2).astype(str) + " %"
            )
            df_senaste = df_senaste.rename(
                columns={"sektor_namn": "Sektor", "förändring": "Utveckling"}
            )

            st.dataframe(df_senaste, hide_index=True)
        else:
            st.warning("Kunde inte ladda sektordata just nu. Försök igen om en stund.")
    else:
        st.error("🔒 Sektorrotation kräver Finestra Advance")

    st.divider()
    st.write("### Djupgående analyser")
    if has_access(st.session_state["user_tier"], "deep_analysis"):
        st.info("Här visas exklusiv marknadsanalys för medlemmar.")
    else:
        st.warning("🔒 Djupanalyser kräver Finestra Advance.")

# --- PRICING ---
with tabs[2]:
  st.markdown(
      "<h2 style='text-align: center;'>Välj din nivå</h2>", unsafe_allow_html=True
  )
  st.write("")

  col1, col2, col3 = st.columns(3)

  with col1:
    st.markdown("""
        ### Insight
        *Håll koll på marknadens topp-aktier.*
        * **De 4 aktierna med högst Finestra score**
        * Visar nuvarande pris, genomsnittligt målpris, % uppsida samt antal köprekar
        * **Månadsbrev:** Nyheter och smakprov på våra analyser direkt i din inkorg.
        
        **Pris: 0 kr/mån**
        """)
    if st.button("Välj Insight"):
      st.session_state["user_tier"] = "insight"
      st.rerun()

  with col2:
    st.markdown("""
        ### Advance
        *För den seriösa aktieinvesteraren.*
        * **Allt i Insight**
        * **Full tillgång till alla aktier & sektorer**
        * **Marknads- och investeringsskola:** Vad påverkar aktierna? Vad är P/E?
        
        **Pris: 79 kr/mån**
        """)
    if st.button("Välj Advance"):
      st.session_state["user_tier"] = "advance"
      st.rerun()

  with col3:
    st.markdown("""
        ### Master
        *För dig som vill ha expertnivå.*
        * **Allt i Advance**
        * **Djupanalyser av utvalda aktier (på webben)**
        * **Avancerade marknadsanalyser:** Guld, silver, olja, krypto & råvaror.
        * **Exklusiva månadsrapporter:** Djupdykningar & nulägesanalyser.
        
        **Pris: 99 kr/mån**
        """)
    if st.button("Välj Master"):
      st.session_state["user_tier"] = "master"
      st.rerun()

# --- FAQ ---
with tabs[3]:
  st.markdown(
      "<h2 style='text-align: center;'>Vanliga frågor och svar</h2>",
      unsafe_allow_html=True,
  )
  st.write("")

  with st.expander("Vad är Finestra Analytics?"):
    st.write(
        "Finestra Analytics är en digital plattform som kombinerar datadrivna"
        " aktieanalyser, sektorrotation och djupgående marknadsutbildning för"
        " att hjälpa dig göra bättre investeringsbeslut."
    )

  with st.expander("Vad är Finestra score?"):
    st.write(
        "Finestra score är vårt egna sammanvägda betyg som rankar aktier"
        " baserat på flera olika kvantitativa parametrar. Det hjälper dig att"
        " snabbt sålla ut vilka bolag som presterar starkast enligt vår modell."
    )

  with st.expander("Fungerar verkligen Finestra Score?"):
    st.write("""
        Vi använder modellen själva i våra egna investeringar, och vi delar med oss av resultat och utveckling i vårt månadsbrev (som ingår gratis i Insight). 
        
        Historisk avkastning är naturligtvis ingen garanti för framtida resultat, och exakt tidshorisont kan variera. Syftet med Finestra Score och våra analysverktyg är att ge dig ett strukturerat ramverk som ökar dina odds och din sannolikhet att göra lönsamma investeringar över tid.
        """)

  with st.expander(
      "Vad är skillnaden mellan Insight, Advance och Master?"
  ):
    st.write("""
        - **Insight (0 kr/mån):** Ger dig de 4 aktierna med högst Finestra score (inkl. nuvarande pris, målpris och uppsida) samt vårt månadsbrev.
        - **Advance (79 kr/mån):** Allt i Insight, plus full tillgång till alla aktier och sektorer samt vår marknads- och investeringsskola där vi förklarar nyckeltal som P/E och vad som driver marknaden.
        - **Master (99 kr/mån):** Allt i Advance, plus våra exklusiva djupanalyser av utvalda aktier, avancerade analyser av råvaror/krypto och våra månatliga fördjupningsrapporter – allt samlat direkt på hemsidan.
        """)

  with st.expander("Hur ofta uppdateras innehållet?"):
    st.write(
        "Topplistan och marknadsdata uppdateras löpande. Vårt"
        " utbildningsmaterial och våra djupanalyser/rapporter uppdateras"
        " regelbundet för att säkerställa högsta kvalitet."
    )

  with st.expander("Kan jag säga upp min prenumeration när som helst?"):
    st.write(
        "Ja, absolut. Det är ingen bindningstid, du avslutar enkelt din"
        " prenumeration direkt via ditt konto när du vill."
    )

  with st.expander("Ger ni personliga finansiella råd?"):
    st.write(
        "Nej. Finestra Analytics tillhandahåller analysverktyg, marknadsdata"
        " och utbildning. Alla investeringar sker på eget ansvar."
    )

# --- KONTO ---
with tabs[4]:
  st.subheader("Konto - Simulator & Information")


  def ändra_nivå():
    st.session_state["user_tier"] = st.session_state["vald_nivå"]


  st.selectbox(
      "Simulera användarnivå (för test):",
      ["insight", "advance", "master"],
      key="vald_nivå",
      on_change=ändra_nivå,
      index=["insight", "advance", "master"].index(
          st.session_state.get("user_tier", "insight")
      ),
  )
  st.write(f"Aktiv nivå i simulatorn: **{st.session_state['user_tier']}**")

# --- INSTÄLLNINGAR ---
with tabs[5]:
  st.subheader("Inställningar")
  st.write("Här kan du hantera dina kontoinställningar framöver.")