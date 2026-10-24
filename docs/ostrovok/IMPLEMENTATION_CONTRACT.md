# О!Собрано: implementation contract

Implementation date: 2026-10-24. User requires free OpenCode models and actual open-data retrieval.

## HTTP
Single-origin FastAPI 8080. Random HttpOnly SameSite=Lax session cookie; every resource checks ownership. 409 stale version/quote, 422 invalid input, 404 inaccessible resource; error {detail:string}.
GET /health; GET /api/capabilities; GET /api/trips -> {trips:[{trip_id,version,status,title,updated_at}]}; POST /api/trips {message,patch?} -> TripState; GET /api/trips/{id}; POST /api/trips/{id}/messages {message,expected_version,patch?}; POST .../selection {plan_id,expected_version}; POST .../quote {expected_version}; POST .../demo-orders {quote_id,expected_version,confirmed:true,total_minor} + Idempotency-Key. All POSTs return full TripState, mutations increment version. GET /api/demo-orders/{id} -> DemoOrder. GET .../events -> SSE recorded actual action/state events. GET/PUT/DELETE /api/preferences -> {preferences:{}}. POST .../service-requests {kind:"early_checkin",message} -> {request_id,status:"requested_demo",message}.

## Intent / allowed partial patch
origin:string|null, destinations:string[], departure_date:YYYY-MM-DD|null, nights:int 2..14, adults:int 1..8, children_ages:int[] 0..17, children_count:int 0..4, pet_kg:number|null 0.1..50, budget_rub:int|null 1000..5000000, max_travel_hours:number|null, transport:any|flight|train, meal:any|breakfast|all_inclusive, refundable:bool, warm:bool, rooms:int 1..4, hotel_preference:any|center|beach, lock_transport:bool. Patch also accepts shift_days:int -60..60. Partial changes preserve other fields. Unknown child age is not zero.
City IDs: moscow, saint-petersburg, kazan, sochi, kaliningrad, yerevan, istanbul, antalya, hurghada. Origins first two; destinations exclude Moscow. Demo dates Nov1 2026–Jan31 2027, return must fit. Relative dates use reference_now + origin_timezone.

## JSON outputs
TripState always includes: trip_id,version,status,intent,reference_now,origin_timezone,plans,selected_plan_id,questions:[{key,label,suggestions:string[]}],assumptions:string[],messages:[{role:user|assistant,text}],delta:null|{changed_fields:string[],preserved_offer_ids:string[],invalidated_offer_ids:string[],price_delta_minor:number|null,summary:string[]},quote,order,action_trace:[{tool,status,detail}],llm:{mode,model:string|null,used:bool,reason:string|null},warnings:string[],locked_component_ids:string[]. Status: needs_clarification|ready|no_options|needs_resolution|ordered.
TripPlan: {plan_id,destination:{id,name,country},title,total_minor,currency:"RUB",components:Offer[],timeline:[{at,label,detail}],validation:{passed,issues:[{rule_id,status,severity,message}]},reasons:string[],tradeoffs:string[],useful_hours:number,weather:object|null}.
Offer: {offer_id,kind:transport|hotel|transfer,title,total_minor,currency:"RUB",details:object,source:{kind:"synthetic",name,url,observed_at},expires_at}. Three components: return transport, entire hotel stay, both transfers. Integer kopecks, total=sum(components).
Quote: {quote_id,plan_id,plan_version,total_minor,currency,expires_at,requires_confirmation:true}.
DemoOrder: {order_id,trip_id,quote_id,total_minor,currency,status:"simulated_confirmed",created_at,plan:TripPlan}. No real payments.
Capabilities: {llm:{mode,primary_model,fallback_model,free_only:true},catalog:{origins:[{id,name}],destinations:[{id,name}],date_from,date_to,min_nights,max_nights},data_sources:[]}.

## Model adapter
Async ModelGateway.extract(message:str,intent:dict,reference_now:str)->dict returns {patch:dict,model:str|null,used:bool,reason:str|null}. Official CLI, all tools denied, isolated env/config, allowlisted free models only. LLM_MODE=opencode|offline; default opencode, visible limited-parser fallback. No session/order authority passed to model.

## UI
Russian, cream/navy/coral, responsive 390px. Left request and editable compact conditions; right comparison, timeline/cart. API-backed history/reload, delta, explicit quote checkbox, receipt. Label demo data and limited mode. Display assistant and actual tool trace. Labelled inputs and focus styles. Playwright: create->compare->change->select->quote->consent->receipt->reload. No fixed canned dialogue, hardcoded IDs or prices. All actions should work.

## Final contract refinements

`pet_requested:boolean` records a pet even when weight is unknown; this blocks comparison until weight is specified or pet is explicitly removed. `return_by:YYYY-MM-DD|null` is an explicit home-arrival deadline and moves with shift_days. `refundable` applies to transport, hotel and transfers. `unresolved_constraints:string[]` persists unsupported hard requirements; unrelated changes never clear them. Only the explicit removal command removes them. `reference_now` is refreshed for each user turn; already resolved dates remain unchanged unless edited. `/health` queries SQLite and returns 503 when storage is unusable.

## Final review fixes (2026-10-24)

An explicitly supplied `patch` (including `{}`) is an authoritative form operation: only its fields are applied, with normal type/date validation and version checks. The accompanying `message` is display copy and is not parsed or sent to the model. Natural-language extraction requires omitting `patch`. Form responses report `llm.used=false`, `llm.reason="explicit_form_patch"`; this is not model inference evidence.

`field_issues:{departure_date?:string}` holds resolvable date questions separately from `unresolved_constraints`. Explicit valid date answers or date form patches resolve only the date question; unrelated hard requirements remain. Pre-fix stored date strings are migrated on the next turn. Unsupported geography remains represented by `unsupported:<name>` in the typed intent route fields and cannot be erased by an incomplete model output or unrelated edit. An explicit route replacement resolves that coverage condition.

TripState includes `service_requests:[{request_id,kind:"early_checkin",status:"requested_demo",message}]`, hydrated from owned durable records on read. POST service-requests returns the same record shape; repeated requests of the same kind for the same owned trip return the original record. This auxiliary request does not change trip version, order, price or consent. It never notifies a supplier. The restored UI displays its recorded demo status.

The model extraction deadline includes semaphore queue wait; queue expiry reports `model_timeout` with `used=false`. Official CLI/free-only allowlist and process cleanup boundaries remain unchanged.
