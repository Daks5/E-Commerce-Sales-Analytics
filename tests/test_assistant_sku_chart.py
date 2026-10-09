"""Regression: SKU results must not visually sum rows into category bars."""
import base64
import json
import numpy as np
from streamlit.testing.v1 import AppTest
from assistant.config import ROOT


def test_maharashtra_sku_chart_preserves_individual_product_values():
    ui = AppTest.from_file(str(ROOT/'assistant/app.py'), default_timeout=45).run()
    ui.selectbox[0].set_value('sku_rank_within_category')
    ui.selectbox[2].set_value('MAHARASHTRA')
    ui.number_input[0].set_value(200)
    ui.button(key='FormSubmitter:explorer-Run analysis').click().run()
    assert not ui.exception
    frame = ui.dataframe[0].value.head(20)
    chart = json.loads(ui.get('plotly_chart')[0].proto.spec)
    trace = chart['data'][0]
    assert list(trace['y']) == list(frame.sku)
    assert len(set(trace['y'])) == len(frame)
    values = trace['x']
    if isinstance(values, dict):
        values = np.frombuffer(base64.b64decode(values['bdata']), dtype=values['dtype'])
    assert list(values) == list(frame.shipped_value)
    kurta = frame[frame.category == 'Kurta']
    assert len(kurta) == 5
    assert kurta.shipped_value.sum() == 117562
    assert kurta.shipped_value.max() == 30177
