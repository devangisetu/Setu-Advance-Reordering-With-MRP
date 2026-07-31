DROP FUNCTION IF EXISTS public.update_product_subcontract_history(integer[], date, date, integer);
CREATE OR REPLACE FUNCTION public.update_product_subcontract_history(
    IN orderpoint_ids integer[],
    IN start_date date,
    IN end_date date,
    IN uid integer
)
RETURNS void AS
$BODY$
BEGIN
    -- Delete existing records for these orderpoints
    DELETE FROM product_subcontract_history
    WHERE orderpoint_id = ANY(orderpoint_ids);

    -- Insert new history records
    INSERT INTO product_subcontract_history (
        orderpoint_id,
        product_id,
        warehouse_id,
        purchase_id,
        partner_id,
        currency_id,
        po_date,
        po_qty,
        purchase_price,
        lead_time,
        create_uid,
        write_uid,
        create_date,
        write_date
    )
    SELECT 
        res.orderpoint_id,
        res.product_id,
        res.warehouse_id,
        res.purchase_id,
        res.partner_id,
        res.currency_id,
        res.po_date,
        res.po_qty,
        res.purchase_price,
        res.lead_time,
        uid,
        uid,
        now() AT TIME ZONE 'UTC',
        now() AT TIME ZONE 'UTC'
    FROM get_product_subcontract_history(orderpoint_ids, start_date, end_date) res;

END; $BODY$
LANGUAGE plpgsql VOLATILE
COST 100;
