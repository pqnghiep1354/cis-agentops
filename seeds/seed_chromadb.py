"""
CIS AgentOps — ChromaDB Seeder
Seeds the vector store with high-quality tour content examples (few-shots).
Run once after `docker compose up -d`.

Usage: python seeds/seed_chromadb.py
"""
import os
import sys
import json

sys.path.insert(0, "..")

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = "cis_few_shots"

# High-quality example content (brand-voice compliant)
FEW_SHOT_EXAMPLES = [
    {
        "id": "fs-001",
        "document": (
            "Designed for the seasoned traveller who values stillness over spectacle, "
            "this eleven-day traverse moves through the cooler highlands of northern Thailand "
            "at a considered pace. Each morning begins before the mist lifts from the Oolong "
            "terraces above Doi Mae Salong — a landscape shaped as much by Yunnanese settlers "
            "as by the mountain itself. The route west toward Mae Hong Son follows forest trails "
            "that see few visitors outside the dry season, passing through Akha and Lisu "
            "settlements where the pace of life is dictated by harvest rather than tourism. "
            "Accommodation is selected for position: a ridge-top lodge with uninterrupted views "
            "of the Pai River valley, a converted teak house in a Karen village, a private wing "
            "of a century-old merchant's residence in Mae Hong Son town."
        ),
        "metadata": {
            "tour_name": "Northern Highlands Traverse",
            "destination": "Thailand",
            "quality_score": 9.2,
            "tags": "highlands,trekking,culture,luxury",
        }
    },
    {
        "id": "fs-002",
        "document": (
            "Bhutan's Lhuentse district receives fewer than three hundred international visitors "
            "each year. This seven-day journey into the kingdom's most restricted valley system "
            "is built around that fact — a curated experience for those who have already seen "
            "Paro and Thimphu, and are ready for something that requires a different kind of "
            "patience. The itinerary moves between dzongs that have not yet been restored for "
            "tourism, monasteries accessible only on foot, and farming communities where the "
            "annual black-necked crane migration marks the calendar as reliably as any festival. "
            "Your guide speaks three dialects of Dzongkha and has been making this circuit for "
            "eleven years. Accommodation is in a private camp designed specifically for this "
            "route, positioned each evening for the best morning light."
        ),
        "metadata": {
            "tour_name": "Lhuentse Valley Expedition",
            "destination": "Bhutan",
            "quality_score": 9.5,
            "tags": "restricted,culture,trekking,exclusive",
        }
    },
    {
        "id": "fs-003",
        "document": (
            "The Mekong moves differently through northern Laos — slower, more deliberate, "
            "its surface unmarked by the boat traffic that defines the southern stretches. "
            "This ten-day journey follows the river from Huay Xai to Luang Prabang by private "
            "slow boat, stopping where the current allows rather than where the timetable demands. "
            "Mornings are spent in villages where the local economy still runs on barter and "
            "weaving; afternoons drift through limestone karst country that has changed little "
            "in the past century. The boat itself — a converted rice barge, refitted with "
            "teakwood interiors and en-suite cabins — carries eight passengers at most. "
            "Each evening anchors at a location chosen for quiet rather than proximity to "
            "the nearest town."
        ),
        "metadata": {
            "tour_name": "Mekong Private Drift",
            "destination": "Laos",
            "quality_score": 9.0,
            "tags": "river,slow-travel,private,culture",
        }
    },
    {
        "id": "fs-004",
        "document": (
            "Tibet at altitude demands a different kind of traveller — one who has made peace "
            "with discomfort and is drawn to landscapes that exist at the edge of what the body "
            "finds comfortable. This twelve-day circuit across the northern plateau moves through "
            "terrain that tests both physical and psychological limits, from the vast stillness "
            "of Lake Namtso at 4,718 metres to the wind-sculpted gullies of the Changtang, "
            "where nomadic herders follow grazing patterns unchanged for generations. "
            "The journey is supported by a specialist team with twenty years of plateau experience, "
            "medical altitude protocols, and accommodation that transitions between fixed lodges "
            "and mobile camp depending on position. Permits for this route are limited to "
            "forty-eight travellers per year."
        ),
        "metadata": {
            "tour_name": "Northern Plateau Crossing",
            "destination": "Tibet",
            "quality_score": 9.3,
            "tags": "altitude,remote,expedition,permits-required",
        }
    },
    {
        "id": "fs-005",
        "document": (
            "Japan's Kii Peninsula has been a pilgrimage route for over twelve centuries, "
            "but the Kumano Kodo trails that connect its three grand shrines were not designed "
            "for speed. This nine-day walk — from Tanabe to Nachi, via the mountain village "
            "of Kumano Hongu — follows stone-paved paths through cedar forests that have never "
            "been logged, past small shrines that predate Buddhism's arrival in Japan, and "
            "through ryokan and minshuku selected for their relationship to the route rather "
            "than their proximity to motorways. The pace is deliberate: fifteen to twenty "
            "kilometres each day, with afternoons that allow for the particular silence of "
            "ancient places. Walking poles, rain gear, and a specialist guide are provided. "
            "The first night begins in Tanabe with a private introduction to the Kumano faith "
            "by a Shinto priest whose family has served this route for six generations."
        ),
        "metadata": {
            "tour_name": "Kumano Kodo Pilgrimage Walk",
            "destination": "Japan",
            "quality_score": 9.4,
            "tags": "pilgrimage,walking,culture,spiritual",
        }
    },
]


def seed_chromadb():
    try:
        import chromadb
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

        # Reset collection if exists
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"Deleted existing collection: {COLLECTION_NAME}")
        except Exception:
            pass

        collection = client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

        ids = [e["id"] for e in FEW_SHOT_EXAMPLES]
        documents = [e["document"] for e in FEW_SHOT_EXAMPLES]
        metadatas = [e["metadata"] for e in FEW_SHOT_EXAMPLES]

        collection.add(ids=ids, documents=documents, metadatas=metadatas)

        count = collection.count()
        print(f"ChromaDB seeded: {count} examples in '{COLLECTION_NAME}'")

        # Verify with test query
        test_results = collection.query(
            query_texts=["luxury trekking highlands Asia private"],
            n_results=2
        )
        print(f"Test query returned {len(test_results['documents'][0])} results")
        for doc in test_results["documents"][0]:
            print(f"  - {doc[:80]}...")

        return True

    except Exception as e:
        print(f"ChromaDB seed failed: {e}")
        print("Make sure ChromaDB is running: docker compose up -d chromadb")
        return False


if __name__ == "__main__":
    success = seed_chromadb()
    sys.exit(0 if success else 1)
