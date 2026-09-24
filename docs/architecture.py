"""オモイデ工房 アーキテクチャ図（技術スタック）の生成。

  docker compose --profile docs run --rm docs

構成を変えたらこのファイルも直すこと。
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.gcp.compute import Run
from diagrams.gcp.database import Firestore
from diagrams.gcp.ml import AIPlatform
from diagrams.gcp.operations import Logging
from diagrams.gcp.storage import Storage
from diagrams.generic.device import Mobile
from diagrams.programming.flowchart import Action

FONT = "Noto Sans CJK JP"

GRAPH_ATTR = {
    "fontname": FONT,
    "fontsize": "16",
    "bgcolor": "#f3ead9",
    "pad": "0.6",
    "splines": "spline",
    "nodesep": "0.9",
    "ranksep": "1.1",
}
NODE_ATTR = {"fontname": FONT, "fontsize": "11", "fontcolor": "#3d332a"}
EDGE_ATTR = {"fontname": FONT, "fontsize": "10", "color": "#8a7a63"}


def cluster(bg: str = "#fffdf7") -> dict[str, str]:
    return {"fontname": FONT, "fontsize": "13", "bgcolor": bg, "pencolor": "#dccdaa", "margin": "16"}


def main() -> None:
    with Diagram(
        "オモイデ工房 — 技術スタック",
        filename="architecture",
        outformat="png",
        show=False,
        direction="TB",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        with Cluster("クライアント", graph_attr=cluster()):
            pwa = Mobile("スマホPWA\nReact + Vite")

        with Cluster("実行基盤 — Cloud Run", graph_attr=cluster("#f7f1e4")):
            api = Run("api\nFastAPI (Python)")
            agent = Run("agent\nAgent Development Kit\n推定／旅程")

        with Cluster("AI・外部 API", graph_attr=cluster()):
            gemini = AIPlatform("Gemini 3.7 Flash\n場所・年代の推定")
            ekispert = Action("駅すぱあと API\nMCP サーバー")

        with Cluster("データ", graph_attr=cluster()):
            gcs = Storage("Cloud Storage\n家族限定・非学習領域")
            fs = Firestore("Firestore\nアルバム・写真・旅程")
            log = Logging("Cloud Logging\n監査ログ")

        pwa >> api
        api >> agent
        agent >> [gemini, ekispert]
        api >> [gcs, fs, log]


if __name__ == "__main__":
    main()
    print("architecture.png を出力しました")
