DROP FUNCTION IF EXISTS public.get_products_production_warehouse_group_wise(integer[], integer[], integer[], integer[], date, date);
CREATE OR REPLACE FUNCTION public.get_products_production_warehouse_group_wise(
    IN company_ids integer[],
    IN product_ids integer[],
    IN category_ids integer[],
    IN warehouse_ids integer[],
    IN start_date date,
    IN end_date date)
RETURNS TABLE(product_id integer, product_name character varying, warehouse_id integer, consumed_qty numeric, ads numeric) AS
$BODY$
    DECLARE
        day_difference integer := ((end_date::Date - start_date::Date) + 1);
    BEGIN

    RETURN QUERY
    Select
        T.product_id,
        T.product_name,
        T.warehouse_id,
        sum(T.product_qty) as consumed_qty,
        case when day_difference > 0 AND sum(T.product_qty) > 0
            then sum(T.product_qty) / day_difference
            else 0
        end as ads
    From
        get_stock_data(company_ids, product_ids, category_ids, warehouse_ids, 'production_out', start_date, end_date) T
    group by
        T.product_id, T.product_name, T.warehouse_id;

END; $BODY$
LANGUAGE plpgsql VOLATILE
COST 100
ROWS 1000;
