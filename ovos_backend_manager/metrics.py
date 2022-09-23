import json
import os
import time

from cutecharts.charts import Pie
from ovos_local_backend.database.metrics import JsonMetricDatabase
from ovos_local_backend.database.settings import DeviceDatabase
from ovos_local_backend.database.utterances import JsonUtteranceDatabase
from ovos_local_backend.database.wakewords import JsonWakeWordDatabase
from pywebio.input import actions
from pywebio.output import put_text, popup, put_code, put_markdown, put_html, use_scope, put_image


def device_select(back_handler=None):
    devices = {uuid: f"{device['name']}@{device['device_location']}"
               for uuid, device in DeviceDatabase().items()}
    buttons = [{'label': "All Devices", 'value': "all"}] + \
              [{'label': d, 'value': uuid} for uuid, d in devices.items()]
    if back_handler:
        buttons.insert(0, {'label': '<- Go Back', 'value': "main"})

    if devices:
        uuid = actions(label="What device would you like to inspect?",
                       buttons=buttons)
        if uuid == "main":
            metrics_menu(back_handler=back_handler)
            return
        else:
            if uuid == "all":
                uuid = None
            if uuid is not None:
                with use_scope("main_view", clear=True):
                    put_markdown(f"\nDevice: {uuid}")
            metrics_menu(uuid=uuid, back_handler=back_handler)
    else:
        popup("No devices paired yet!")
        metrics_menu(back_handler=back_handler)


def metrics_select(back_handler=None, uuid=None):
    buttons = []
    db = JsonMetricDatabase()
    if not len(db):
        with use_scope("main_view", clear=True):
            put_text("No metrics uploaded yet!")
        metrics_menu(back_handler=back_handler, uuid=uuid)
        return

    for m in db:
        name = f"{m['metric_id']}-{m['metric_type']}"
        if uuid is not None and m["uuid"] != uuid:
            continue
        buttons.append({'label': name, 'value': m['metric_id']})
    if back_handler:
        buttons.insert(0, {'label': '<- Go Back', 'value': "main"})
    opt = actions(label="Select a metric to inspect",
                  buttons=buttons)
    if opt == "main":
        device_select(back_handler=back_handler)
        return
    # id == db_position + 1
    with use_scope("main_view", clear=True):
        put_markdown("# Metadata")
        put_code(json.dumps(db[opt - 1], indent=4), "json")
    metrics_select(back_handler=back_handler, uuid=uuid)


def metrics_menu(back_handler=None, uuid=None):
    with use_scope("logo", clear=True):
        img = open(f'{os.path.dirname(__file__)}/res/metrics.png', 'rb').read()
        put_image(img)

    buttons = [{'label': 'Metric Types', 'value': "types"},
               {'label': 'Intents', 'value': "intents"},
               {'label': 'FallbackSkill', 'value': "fallback"},
               {'label': 'STT', 'value': "stt"},
               {'label': 'TTS', 'value': "tts"},
               {'label': 'Wake Words', 'value': "ww"},
               {'label': 'Open Dataset', 'value': "opt-in"}]
    if uuid is not None:
        buttons.append({'label': 'Delete Device metrics', 'value': "delete_metrics"})
    else:
        buttons.insert(1, {'label': 'Devices', 'value': "devices"})
        buttons.append({'label': 'Inspect Devices', 'value': "metrics"})
        buttons.append({'label': 'Delete ALL metrics', 'value': "delete_metrics"})

    if back_handler:
        buttons.insert(0, {'label': '<- Go Back', 'value': "main"})

    opt = actions(label="What would you like to do?",
                  buttons=buttons)
    if uuid is not None:
        m = DeviceMetricsReportGenerator(uuid)
    else:
        m = MetricsReportGenerator()
    if opt == "opt-in":
        with use_scope("main_view", clear=True):
            if uuid is None:
                md = f"""# Open Dataset Report
            Total Registered Devices: {len(DeviceDatabase())}
            Currently Opted-in: {len([d for d in DeviceDatabase() if d.opt_in])}
            Unique Devices seen: {m.total_devices}"""
            else:
                md = f"""Device: {uuid}
            
            # Open Dataset Report"""

            md += f"""
            
            Total Metrics submitted: {m.total_metrics}
            Total WakeWords submitted: {m.total_ww}
            Total Utterances submitted: {m.total_utt}"""

            put_markdown(md)
            put_html(m.optin_chart().render_notebook())
    if opt == "devices":
        with use_scope("main_view", clear=True):
            md = f"""# Devices Report
            Total Devices: {m.total_devices}

            Total untracked: {len(m.untracked_devices)}
            Total active (estimate): {len(m.active_devices)}
            Total dormant (estimate): {len(m.dormant_devices)}"""
            put_markdown(md)
            put_html(m.device_chart().render_notebook())
    if opt == "intents":
        with use_scope("main_view", clear=True):
            txt_estimate = max(m.total_intents + m.total_fallbacks - m.total_stt, 0)
            stt_estimate = max(m.total_intents + m.total_fallbacks - txt_estimate, 0)
            if uuid is not None:
                put_markdown(f"\nDevice: {uuid}")
            md = f"""# Intent Matches Report
            Total queries: {m.total_intents + m.total_fallbacks}
            
            Total text queries (estimate): {txt_estimate}
            Total speech queries (estimate): {stt_estimate}
            
            Total Matches: {m.total_intents}"""
            put_markdown(md)
            put_html(m.intent_type_chart().render_notebook())
    if opt == "ww":
        bad = max(0, m.total_stt - m.total_ww)
        silents = max(0, m.total_stt - m.total_utt)
        with use_scope("main_view", clear=True):
            if uuid is not None:
                put_markdown(f"\nDevice: {uuid}\n\n")
            put_markdown(f"""Total WakeWord uploads: {m.total_ww}
            
            Total WakeWord detections (estimate): {m.total_stt}
            False Activations (estimate): {bad or silents}
            Silent Activations (estimate): {silents}""")
            put_html(m.ww_chart().render_notebook())
    if opt == "stt":
        silents = max(0, m.total_stt - m.total_utt)
        with use_scope("main_view", clear=True):
            if uuid is not None:
                put_markdown(f"\nDevice: {uuid}\n\n")
            put_markdown(f"""Total Transcriptions: {m.total_stt}
            Total Recording uploads: {m.total_utt}
            
            Silent Activations (estimate): {silents}""")
            put_html(m.stt_type_chart().render_notebook())
    if opt == "tts":
        with use_scope("main_view", clear=True):
            if uuid is not None:
                put_markdown(f"\nDevice: {uuid}")
            put_html(m.tts_type_chart().render_notebook())
    if opt == "types":
        with use_scope("main_view", clear=True):
            if uuid is not None:
                put_markdown(f"\nDevice: {uuid}")
            put_markdown(f"""
        # Metrics Report
        
        Total Intents: {m.total_intents}
        Total Fallbacks: {m.total_fallbacks}
        Total Transcriptions: {m.total_stt}
        Total TTS: {m.total_tts}
        """)
            put_html(m.metrics_type_chart().render_notebook())
    if opt == "fallback":
        with use_scope("main_view", clear=True):
            if uuid is not None:
                put_markdown(f"\nDevice: {uuid}")
            f = 0
            if m.total_intents + m.total_fallbacks > 0:
                f = m.total_intents / (m.total_intents + m.total_fallbacks)
            put_markdown(f"""
                        # Fallback Matches Report

                        Total queries: {m.total_intents + m.total_fallbacks}
                        Total Intents: {m.total_intents}
                        Total Fallbacks: {m.total_fallbacks}

                        Failure Percentage (estimate): {1 - f}
                        """)
            put_html(m.fallback_type_chart().render_notebook())
    if opt == "metrics":
        device_select(back_handler=back_handler)
    if opt == "delete_metrics":
        if uuid is not None:
            with use_scope("main_view", clear=True):
                put_markdown(f"\nDevice: {uuid}")
        with popup("Are you sure you want to delete the metrics database?"):
            put_text("this can not be undone, proceed with caution!")
            put_text("ALL metrics will be lost")
        opt = actions(label="Delete metrics database?",
                      buttons=[{'label': "yes", 'value': True},
                               {'label': "no", 'value': False}])
        if opt:
            os.remove(JsonMetricDatabase().db.path)
            with use_scope("main_view", clear=True):
                if back_handler:
                    back_handler()
        else:
            metrics_menu(back_handler=back_handler, uuid=uuid)
        return
    if opt == "main":
        with use_scope("main_view", clear=True):
            if uuid is not None:
                device_select(back_handler=back_handler)
            elif back_handler:
                back_handler()
        return
    metrics_menu(back_handler=back_handler, uuid=uuid)


class MetricsReportGenerator:
    def __init__(self):
        self.total_intents = 0
        self.total_fallbacks = 0
        self.total_stt = 0
        self.total_tts = 0
        self.total_ww = len(JsonWakeWordDatabase())
        self.total_utt = len(JsonUtteranceDatabase())
        self.total_devices = len(DeviceDatabase())
        self.total_metrics = len(JsonMetricDatabase())

        self.intents = {}
        self.fallbacks = {}
        self.ww = {}
        self.tts = {}
        self.stt = {}
        self.devices = {}
        self.load_metrics()

    @property
    def active_devices(self):
        thresh = time.time() - 7 * 24 * 60 * 60
        return [uuid for uuid, ts in self.devices.items()
                if ts > thresh and uuid not in self.untracked_devices]

    @property
    def dormant_devices(self):
        return [uuid for uuid in self.devices.keys()
                if uuid not in self.untracked_devices
                and uuid not in self.active_devices]

    @property
    def untracked_devices(self):
        return [dev.uuid for dev in DeviceDatabase() if not dev.opt_in]

    def device_chart(self):
        chart = Pie("Devices")
        chart.set_options(
            labels=["active", "dormant", "untracked"],
            inner_radius=0,
        )
        chart.add_series([len(self.active_devices),
                          len(self.dormant_devices),
                          len(self.untracked_devices)])
        return chart

    def ww_chart(self):
        chart = Pie("Wake Words")
        labels = []
        series = []
        for ww, count in self.ww.items():
            labels.append(ww)
            series.append(count)

        chart.set_options(
            labels=labels,
            inner_radius=0,
        )
        chart.add_series(series)
        return chart

    def optin_chart(self):
        chart = Pie("Uploaded Data")
        chart.set_options(
            labels=["wake-words", "utterances", "metrics"],
            inner_radius=0,
        )
        chart.add_series([self.total_ww, self.total_utt, self.total_metrics])
        return chart

    def metrics_type_chart(self):
        chart = Pie("Metric Types")
        chart.set_options(
            labels=["intents", "fallbacks", "stt", "tts"],
            inner_radius=0,
        )
        chart.add_series([self.total_intents,
                          self.total_fallbacks,
                          self.total_stt,
                          self.total_tts])
        return chart

    def intent_type_chart(self):
        chart = Pie("Intent Matches")
        chart.set_options(
            labels=list(self.intents.keys()),
            inner_radius=0,
        )
        chart.add_series(list(self.intents.values()))
        return chart

    def fallback_type_chart(self):
        chart = Pie("Fallback Skills")
        chart.set_options(
            labels=list(self.fallbacks.keys()),
            inner_radius=0,
        )
        chart.add_series(list(self.fallbacks.values()))
        return chart

    def tts_type_chart(self):
        chart = Pie("Text To Speech Engines")
        chart.set_options(
            labels=list(self.tts.keys()),
            inner_radius=0,
        )
        chart.add_series(list(self.tts.values()))
        return chart

    def stt_type_chart(self):
        chart = Pie("Speech To Text Engines")
        chart.set_options(
            labels=list(self.stt.keys()),
            inner_radius=0,
        )
        chart.add_series(list(self.stt.values()))
        return chart

    def reset_metrics(self):
        self.total_intents = 0
        self.total_fallbacks = 0
        self.total_stt = 0
        self.total_tts = 0
        self.total_ww = len(JsonWakeWordDatabase())
        self.total_metrics = len(JsonMetricDatabase())
        self.total_utt = len(JsonUtteranceDatabase())
        self.total_devices = 0

        self.intents = {}
        self.devices = {}
        self.fallbacks = {}
        self.tts = {}
        self.stt = {}
        self.ww = {}

    def load_metrics(self):
        self.reset_metrics()
        for m in JsonMetricDatabase():
            if m["uuid"] not in self.devices:
                self.total_devices += 1
            self._process_metric(m)
        for ww in JsonWakeWordDatabase():
            if ww["meta"]["name"] not in self.ww:
                self.ww[ww["meta"]["name"]] = 0
            else:
                self.ww[ww["meta"]["name"]] += 1

    def _process_metric(self, m):
        if m["uuid"] not in self.devices or \
                m["meta"]["time"] > self.devices[m["uuid"]]:
            self.devices[m["uuid"]] = m["meta"]["time"]
        if m["metric_type"] == "intent_service":
            self.total_intents += 1
            k = f"{m['meta']['intent_type']}"
            if k not in self.intents:
                self.intents[k] = 0
            self.intents[k] += 1
        if m["metric_type"] == "fallback_handler":
            self.total_fallbacks += 1
            k = f"{m['meta']['handler']}"
            if m['meta'].get("skill_id"):
                k = f"{m['meta']['skill_id']}:{m['meta']['handler']}"
            if k not in self.fallbacks:
                self.fallbacks[k] = 0
            self.fallbacks[k] += 1
        if m["metric_type"] == "stt":
            self.total_stt += 1
            k = f"{m['meta']['stt']}"
            if k not in self.stt:
                self.stt[k] = 0
            self.stt[k] += 1
        if m["metric_type"] == "speech":
            self.total_tts += 1
            k = f"{m['meta']['tts']}"
            if k not in self.tts:
                self.tts[k] = 0
            self.tts[k] += 1


class DeviceMetricsReportGenerator(MetricsReportGenerator):
    def __init__(self, uuid):
        self.uuid = uuid
        super().__init__()

    def load_metrics(self):
        self.reset_metrics()

        self.total_ww = len([ww for ww in JsonWakeWordDatabase()
                             if ww["uuid"] == self.uuid])
        self.total_metrics = 0
        self.total_utt = len([utt for utt in JsonUtteranceDatabase()
                              if utt["uuid"] == self.uuid])

        for m in JsonMetricDatabase():
            if m["uuid"] != self.uuid:
                continue
            self._process_metric(m)
            self.total_metrics += 1
        for ww in JsonWakeWordDatabase():
            if ww["uuid"] != self.uuid:
                continue
            if ww["meta"]["name"] not in self.ww:
                self.ww[ww["meta"]["name"]] = 0
            else:
                self.ww[ww["meta"]["name"]] += 1


if __name__ == "__main__":
    for ww in JsonWakeWordDatabase():
        print(ww)
