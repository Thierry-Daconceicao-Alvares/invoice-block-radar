select
    case_id,
    po_document,
    po_item,
    item_category,
    item_type,
    document_type,
    doc_category,
    gr_based_iv,
    goods_receipt as goods_receipt_expected,
    company,
    vendor,
    spend_area,
    sub_spend_area,
    spend_classification,
    source_system
from {{ source('bpi2019', 'items') }}
