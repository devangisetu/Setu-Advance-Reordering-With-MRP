DROP FUNCTION IF EXISTS public.get_products_resupply_history_data(integer[], integer[], integer[], integer[], date, date);
CREATE OR REPLACE FUNCTION public.get_products_resupply_history_data(
    IN company_ids integer[],
    IN product_ids integer[],
    IN category_ids integer[],
    IN warehouse_ids integer[],
    IN start_date date,
    IN end_date date)
  RETURNS TABLE(company_id integer, product_id integer, product_category_id integer, warehouse_id integer, resupply_qty numeric, total_resupply_orders numeric, average_daily_resupply numeric, maximum_daily_resupply numeric, minimum_daily_resupply numeric, total_resupply_qty numeric, resupply_return_qty numeric) AS
$BODY$
    DECLARE
        end_date date:= (case when CURRENT_DATE <= end_date::date and CURRENT_DATE >=start_date::date then CURRENT_DATE else end_date END);
        day_difference integer := ((end_date::Date-start_date::Date)+1);
        tr_start_date timestamp without time zone := (start_date || ' 00:00:00')::timestamp without time zone;
        tr_end_date timestamp without time zone:= (end_date || ' 23:59:59')::timestamp without time zone;
    BEGIN
    Return Query
    Select
        sd.cmp_id,
        sd.p_id,
        sd.categ_id,
        sd.wh_id,
        sum(sd.resupply_qty) - sum(sd.resupply_return_qty) as resupply_qty,
        sum(sd.total_orders) as total_resupply_orders,
        case when (sum(sd.resupply_qty) - sum(sd.resupply_return_qty)) <= 0 then 0 else
        round((sum(sd.resupply_qty) - sum(sd.resupply_return_qty)) /day_difference,2) end as average_daily_resupply,
        max(sd.resupply_qty) maximum_daily_resupply,
        --min(sd.total_sales) min_daily_sale,
        MIN(NULLIF(sd.resupply_qty, 0)) minimum_daily_resupply,
        sum(sd.resupply_qty) as total_resupply_qty,
        sum(sd.resupply_return_qty) as resupply_return_qty
    From (
        Select
            cmp_id,
            p_id,
            categ_id,
            wh_id,
            T.order_date,
            sum(T.resupply_qty) as resupply_qty,
            sum(T.resupply_return_qty) as resupply_return_qty,
            count(T.order_id) as total_orders
        From(
                Select
                    foo.cmp_id,
                    foo.p_id,
                    foo.categ_id,
                    foo.wh_id,
                    sum(Round(foo.resupply_qty,2)) AS resupply_qty,
                    sum(Round(foo.resupply_return_qty,2)) AS resupply_return_qty,
                    foo.order_id,
                    foo.order_date
                From (
                        Select
                            move.company_id AS cmp_id,
                            move.product_id AS p_id,
                            tmpl.categ_id,
                            po.id as order_id,
                            CASE WHEN dest.is_subcontracting_location THEN source_warehouse.id
                                 WHEN source.is_subcontracting_location THEN dest_warehouse.id
                            END AS wh_id,
                            -- po.id AS order_id,
                            move.date::date AS order_date,
                            CASE WHEN source.usage = 'internal'AND dest.usage = 'internal' AND dest.is_subcontracting_location
                                THEN move.product_uom_qty ELSE 0 END AS resupply_qty,
                            CASE WHEN source.usage = 'internal'AND dest.usage = 'internal' AND source.is_subcontracting_location
                                THEN move.product_uom_qty ELSE 0 END AS resupply_return_qty
                        FROM stock_move move
                        Inner Join stock_location source ON source.id = move.location_id
                        Inner Join stock_location dest ON dest.id = move.location_dest_id
                        Inner Join stock_picking picking ON picking.id = move.picking_id
                        Inner Join stock_picking_type spt on spt.id = picking.picking_type_id
                        left join stock_picking sp on sp.name = move.origin
                        left join stock_move sm on sm.picking_id = sp.id
                        left join purchase_order_line pol on pol.id = sm.purchase_line_id
                        left join purchase_order po on po.id = pol.order_id
                        Inner Join res_company cmp on cmp.id = move.company_id
                        Inner Join product_product prod ON prod.id = move.product_id
                        Inner Join product_template tmpl ON tmpl.id = prod.product_tmpl_id
                        Inner Join product_category cat on cat.id = tmpl.categ_id
                        Left Join stock_warehouse source_warehouse ON source.parent_path::text ~~ concat('%/', source_warehouse.view_location_id, '/%')
                        Left Join stock_warehouse dest_warehouse ON dest.parent_path::text ~~ concat('%/', dest_warehouse.view_location_id, '/%')
                        WHERE
                            prod.active = true and tmpl.active = true
                            and move.date::date >= tr_start_date and move.date::date <= tr_end_date
                            and move.state = 'done' and spt.code = 'internal'
                            and tmpl.is_storable = True
                            and tmpl.type != 'combo'
                            and (dest.is_subcontracting_location or source.is_subcontracting_location)
                            and 1 = case when array_length(company_ids,1) >= 1 then
                            case when move.company_id = ANY(company_ids) then 1 else 0 end
                            else 1 end
                            --product dynamic condition
                            and 1 = case when array_length(product_ids,1) >= 1 then
                            case when move.product_id = ANY(product_ids) then 1 else 0 end
                            else 1 end
                            --category dynamic condition
                            and 1 = case when array_length(category_ids,1) >= 1 then
                            case when tmpl.categ_id = ANY(category_ids) then 1 else 0 end
                            else 1 end
                            --warehouse dynamic condition
                            and 1 = case when array_length(warehouse_ids,1) >= 1 then
                                        case when source.usage = 'internal' then
                                            case when source_warehouse.id = ANY(warehouse_ids) then 1 else 0 end
                                        else
                                            case when dest_warehouse.id = ANY(warehouse_ids) then 1 else 0 end
                                        end
                                    else 1 end

                        Union All
                        SELECT
                            wh.company_id as cmp_id,
                            pro.id as p_id,
                            pt.categ_id,
                            wh.id as wh_id,
                            null::integer as order_id,
                            start_date::date as order_date,
                            0 as sales_qty,
                            0 as sales_return_qty
                        FROM product_product pro, product_template pt, stock_warehouse wh
                        Where pro.product_tmpl_id = pt.id
                            and 1 = case when array_length(company_ids,1) >= 1 then
                                        case when wh.company_id = ANY(company_ids) then 1 else 0 end
                                    else 1 end
                            --product dynamic condition
                            and 1 = case when array_length(product_ids,1) >= 1 then
                                        case when pro.id = ANY(product_ids) then 1 else 0 end
                                    else 1 end
                            --category dynamic condition
                            and 1 = case when array_length(category_ids,1) >= 1 then
                                        case when pt.categ_id = ANY(category_ids) then 1 else 0 end
                                    else 1 end
                            --warehouse dynamic condition
                            and 1 = case when array_length(warehouse_ids,1) >= 1 then
                                        case when wh.id = ANY(warehouse_ids) then 1 else 0 end
                                    else 1 end
                        )foo
                        group by foo.cmp_id, foo.p_id, foo.order_id, foo.order_date,foo.categ_id,foo.wh_id
                )T
                group by cmp_id, p_id, categ_id, wh_id,  T.order_date
    )sd
    group by cmp_id, p_id, categ_id, wh_id;
    END;
$BODY$
LANGUAGE plpgsql VOLATILE
COST 100
ROWS 1000;