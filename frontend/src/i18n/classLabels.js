// Display-only translations for detector class names and model keys.
//
// The VALUE bound to a form, sent to the API, and stored in the DB must stay
// the exact string a YOLO/HF model actually outputs ("person", "fire",
// "Tomato leaf") - that is the only thing that will ever match what the model
// reports. This file only changes what a human reads on screen; nothing here
// is ever written back to a form field or a request body.
//
// No 'en' key is stored per entry: the raw English string already IS the
// English display text, so English is the implicit fallback for both a
// missing locale and an unrecognised label (a class added later without an
// entry here just shows its raw name, same as it did before this file).

// The 80 standard COCO classes the default YOLOv8 weights were trained on.
const COCO = {
  person: { fr: 'personne', ar: 'شخص', zh: '人' },
  bicycle: { fr: 'vélo', ar: 'دراجة هوائية', zh: '自行车' },
  car: { fr: 'voiture', ar: 'سيارة', zh: '汽车' },
  motorcycle: { fr: 'moto', ar: 'دراجة نارية', zh: '摩托车' },
  airplane: { fr: 'avion', ar: 'طائرة', zh: '飞机' },
  bus: { fr: 'bus', ar: 'حافلة', zh: '公交车' },
  train: { fr: 'train', ar: 'قطار', zh: '火车' },
  truck: { fr: 'camion', ar: 'شاحنة', zh: '卡车' },
  boat: { fr: 'bateau', ar: 'قارب', zh: '船' },
  'traffic light': { fr: 'feu de circulation', ar: 'إشارة مرور', zh: '交通信号灯' },
  'fire hydrant': { fr: "bouche d'incendie", ar: 'صنبور إطفاء', zh: '消防栓' },
  'stop sign': { fr: 'panneau stop', ar: 'إشارة قف', zh: '停车标志' },
  'parking meter': { fr: 'parcmètre', ar: 'عداد وقوف السيارات', zh: '停车计时器' },
  bench: { fr: 'banc', ar: 'مقعد', zh: '长椅' },
  bird: { fr: 'oiseau', ar: 'طائر', zh: '鸟' },
  cat: { fr: 'chat', ar: 'قطة', zh: '猫' },
  dog: { fr: 'chien', ar: 'كلب', zh: '狗' },
  horse: { fr: 'cheval', ar: 'حصان', zh: '马' },
  sheep: { fr: 'mouton', ar: 'خروف', zh: '羊' },
  cow: { fr: 'vache', ar: 'بقرة', zh: '牛' },
  elephant: { fr: 'éléphant', ar: 'فيل', zh: '大象' },
  bear: { fr: 'ours', ar: 'دب', zh: '熊' },
  zebra: { fr: 'zèbre', ar: 'حمار وحشي', zh: '斑马' },
  giraffe: { fr: 'girafe', ar: 'زرافة', zh: '长颈鹿' },
  backpack: { fr: 'sac à dos', ar: 'حقيبة ظهر', zh: '背包' },
  umbrella: { fr: 'parapluie', ar: 'مظلة', zh: '雨伞' },
  handbag: { fr: 'sac à main', ar: 'حقيبة يد', zh: '手提包' },
  tie: { fr: 'cravate', ar: 'ربطة عنق', zh: '领带' },
  suitcase: { fr: 'valise', ar: 'حقيبة سفر', zh: '行李箱' },
  frisbee: { fr: 'frisbee', ar: 'فريسبي', zh: '飞盘' },
  skis: { fr: 'skis', ar: 'زلاجات تزلج', zh: '滑雪板' },
  snowboard: { fr: 'snowboard', ar: 'لوح تزلج على الثلج', zh: '单板滑雪板' },
  'sports ball': { fr: 'ballon de sport', ar: 'كرة رياضية', zh: '运动球' },
  kite: { fr: 'cerf-volant', ar: 'طائرة ورقية', zh: '风筝' },
  'baseball bat': { fr: 'batte de baseball', ar: 'مضرب بيسبول', zh: '棒球棒' },
  'baseball glove': { fr: 'gant de baseball', ar: 'قفاز بيسبول', zh: '棒球手套' },
  skateboard: { fr: 'skateboard', ar: 'لوح تزلج', zh: '滑板' },
  surfboard: { fr: 'planche de surf', ar: 'لوح ركوب الأمواج', zh: '冲浪板' },
  'tennis racket': { fr: 'raquette de tennis', ar: 'مضرب تنس', zh: '网球拍' },
  bottle: { fr: 'bouteille', ar: 'زجاجة', zh: '瓶子' },
  'wine glass': { fr: 'verre à vin', ar: 'كأس نبيذ', zh: '酒杯' },
  cup: { fr: 'tasse', ar: 'كوب', zh: '杯子' },
  fork: { fr: 'fourchette', ar: 'شوكة', zh: '叉子' },
  knife: { fr: 'couteau', ar: 'سكين', zh: '刀' },
  spoon: { fr: 'cuillère', ar: 'ملعقة', zh: '勺子' },
  bowl: { fr: 'bol', ar: 'وعاء', zh: '碗' },
  banana: { fr: 'banane', ar: 'موز', zh: '香蕉' },
  apple: { fr: 'pomme', ar: 'تفاحة', zh: '苹果' },
  sandwich: { fr: 'sandwich', ar: 'شطيرة', zh: '三明治' },
  orange: { fr: 'orange', ar: 'برتقال', zh: '橙子' },
  broccoli: { fr: 'brocoli', ar: 'بروكلي', zh: '西兰花' },
  carrot: { fr: 'carotte', ar: 'جزر', zh: '胡萝卜' },
  'hot dog': { fr: 'hot-dog', ar: 'هوت دوغ', zh: '热狗' },
  pizza: { fr: 'pizza', ar: 'بيتزا', zh: '披萨' },
  donut: { fr: 'beignet', ar: 'دونات', zh: '甜甜圈' },
  cake: { fr: 'gâteau', ar: 'كعكة', zh: '蛋糕' },
  chair: { fr: 'chaise', ar: 'كرسي', zh: '椅子' },
  couch: { fr: 'canapé', ar: 'أريكة', zh: '沙发' },
  'potted plant': { fr: 'plante en pot', ar: 'نبتة أصيص', zh: '盆栽' },
  bed: { fr: 'lit', ar: 'سرير', zh: '床' },
  'dining table': { fr: 'table à manger', ar: 'طاولة طعام', zh: '餐桌' },
  toilet: { fr: 'toilettes', ar: 'مرحاض', zh: '马桶' },
  tv: { fr: 'télé', ar: 'تلفاز', zh: '电视' },
  laptop: { fr: 'ordinateur portable', ar: 'حاسوب محمول', zh: '笔记本电脑' },
  mouse: { fr: 'souris', ar: 'فأرة حاسوب', zh: '鼠标' },
  remote: { fr: 'télécommande', ar: 'جهاز تحكم عن بعد', zh: '遥控器' },
  keyboard: { fr: 'clavier', ar: 'لوحة مفاتيح', zh: '键盘' },
  'cell phone': { fr: 'téléphone portable', ar: 'هاتف محمول', zh: '手机' },
  microwave: { fr: 'micro-ondes', ar: 'ميكروويف', zh: '微波炉' },
  oven: { fr: 'four', ar: 'فرن', zh: '烤箱' },
  toaster: { fr: 'grille-pain', ar: 'محمصة', zh: '烤面包机' },
  sink: { fr: 'évier', ar: 'حوض', zh: '水槽' },
  refrigerator: { fr: 'réfrigérateur', ar: 'ثلاجة', zh: '冰箱' },
  book: { fr: 'livre', ar: 'كتاب', zh: '书' },
  clock: { fr: 'horloge', ar: 'ساعة', zh: '时钟' },
  vase: { fr: 'vase', ar: 'مزهرية', zh: '花瓶' },
  scissors: { fr: 'ciseaux', ar: 'مقص', zh: '剪刀' },
  'teddy bear': { fr: 'ours en peluche', ar: 'دمية دب', zh: '泰迪熊' },
  'hair drier': { fr: 'sèche-cheveux', ar: 'مجفف شعر', zh: '吹风机' },
  toothbrush: { fr: 'brosse à dents', ar: 'فرشاة أسنان', zh: '牙刷' },
}

// The custom fire-detection model's two classes.
const FIRE = {
  fire: { fr: 'feu', ar: 'حريق', zh: '火' },
  smoke: { fr: 'fumée', ar: 'دخان', zh: '烟' },
}

// The 31 PlantDoc classes the "plant" model was fine-tuned on. Translated by
// crop + condition rather than as opaque phrases, for consistency across the
// set; functional/best-effort rather than certified agronomy terminology.
// "Soyabean leaf" and "Soybean leaf" are two distinct labels in the upstream
// dataset (a spelling variant, not a typo here) - both map to the same
// display text on purpose, matching that quirk rather than hiding it.
const PLANT = {
  leaves: { fr: 'feuilles', ar: 'أوراق', zh: '叶片' },
  'Apple Scab Leaf': { fr: 'Feuille de pommier - tavelure', ar: 'ورقة تفاح - جرب', zh: '苹果叶 - 黑星病' },
  'Apple leaf': { fr: 'Feuille de pommier', ar: 'ورقة تفاح', zh: '苹果叶' },
  'Apple rust leaf': { fr: 'Feuille de pommier - rouille', ar: 'ورقة تفاح - صدأ', zh: '苹果叶 - 锈病' },
  'Bell_pepper leaf': { fr: 'Feuille de poivron', ar: 'ورقة فلفل حلو', zh: '甜椒叶' },
  'Bell_pepper leaf spot': { fr: 'Feuille de poivron - taches', ar: 'ورقة فلفل حلو - تبقع', zh: '甜椒叶 - 斑点病' },
  'Blueberry leaf': { fr: 'Feuille de myrtille', ar: 'ورقة توت أزرق', zh: '蓝莓叶' },
  'Cherry leaf': { fr: 'Feuille de cerisier', ar: 'ورقة كرز', zh: '樱桃叶' },
  'Corn Gray leaf spot': { fr: 'Feuille de maïs - taches grises', ar: 'ورقة ذرة - تبقع رمادي', zh: '玉米叶 - 灰斑病' },
  'Corn leaf blight': { fr: 'Feuille de maïs - brûlure', ar: 'ورقة ذرة - لفحة', zh: '玉米叶 - 枯萎病' },
  'Corn rust leaf': { fr: 'Feuille de maïs - rouille', ar: 'ورقة ذرة - صدأ', zh: '玉米叶 - 锈病' },
  'Peach leaf': { fr: 'Feuille de pêcher', ar: 'ورقة خوخ', zh: '桃叶' },
  'Potato leaf': { fr: 'Feuille de pomme de terre', ar: 'ورقة بطاطس', zh: '马铃薯叶' },
  'Potato leaf early blight': { fr: 'Feuille de pomme de terre - mildiou précoce', ar: 'ورقة بطاطس - لفحة مبكرة', zh: '马铃薯叶 - 早疫病' },
  'Potato leaf late blight': { fr: 'Feuille de pomme de terre - mildiou tardif', ar: 'ورقة بطاطس - لفحة متأخرة', zh: '马铃薯叶 - 晚疫病' },
  'Raspberry leaf': { fr: 'Feuille de framboisier', ar: 'ورقة توت العليق', zh: '覆盆子叶' },
  'Soyabean leaf': { fr: 'Feuille de soja', ar: 'ورقة فول الصويا', zh: '大豆叶' },
  'Soybean leaf': { fr: 'Feuille de soja', ar: 'ورقة فول الصويا', zh: '大豆叶' },
  'Squash Powdery mildew leaf': { fr: 'Feuille de courge - oïdium', ar: 'ورقة قرع - بياض دقيقي', zh: '南瓜叶 - 白粉病' },
  'Strawberry leaf': { fr: 'Feuille de fraisier', ar: 'ورقة فراولة', zh: '草莓叶' },
  'Tomato Early blight leaf': { fr: 'Feuille de tomate - mildiou précoce', ar: 'ورقة طماطم - لفحة مبكرة', zh: '番茄叶 - 早疫病' },
  'Tomato Septoria leaf spot': { fr: 'Feuille de tomate - septoriose', ar: 'ورقة طماطم - تبقع سبتوريا', zh: '番茄叶 - 斑枯病' },
  'Tomato leaf': { fr: 'Feuille de tomate', ar: 'ورقة طماطم', zh: '番茄叶' },
  'Tomato leaf bacterial spot': { fr: 'Feuille de tomate - tache bactérienne', ar: 'ورقة طماطم - تبقع بكتيري', zh: '番茄叶 - 细菌性斑点病' },
  'Tomato leaf late blight': { fr: 'Feuille de tomate - mildiou tardif', ar: 'ورقة طماطم - لفحة متأخرة', zh: '番茄叶 - 晚疫病' },
  'Tomato leaf mosaic virus': { fr: 'Feuille de tomate - virus de la mosaïque', ar: 'ورقة طماطم - فيروس الموزاييك', zh: '番茄叶 - 花叶病毒' },
  'Tomato leaf yellow virus': { fr: 'Feuille de tomate - virus des feuilles jaunes', ar: 'ورقة طماطم - فيروس الاصفرار', zh: '番茄叶 - 黄化病毒' },
  'Tomato mold leaf': { fr: 'Feuille de tomate - moisissure', ar: 'ورقة طماطم - عفن', zh: '番茄叶 - 霉病' },
  'Tomato two spotted spider mites leaf': { fr: 'Feuille de tomate - acariens tisserands', ar: 'ورقة طماطم - العنكبوت الأحمر', zh: '番茄叶 - 二斑叶螨' },
  'grape leaf': { fr: 'feuille de vigne', ar: 'ورقة عنب', zh: '葡萄叶' },
  'grape leaf black rot': { fr: 'feuille de vigne - pourriture noire', ar: 'ورقة عنب - العفن الأسود', zh: '葡萄叶 - 黑腐病' },
}

export const LABELS = { ...COCO, ...FIRE, ...PLANT }

// Case-insensitive index. The plant-disease model emits Title Case
// ("Corn leaf blight"), but a rule's label is lowercased on save
// (rule_engine.py) and an alert's label is copied from the rule - so the
// exact same class shows up as "corn leaf blight" depending on which table
// it is read from. An exact-match lookup only ever caught the COCO/fire
// classes, which happen to be lowercase everywhere already; this catches
// every casing without renaming a single key above.
const LABELS_LC = Object.fromEntries(
  Object.entries(LABELS).map(([k, v]) => [k.toLowerCase(), v])
)

// Model keys are env-driven (YOLO_EXTRA_MODELS / HF_MODELS - see
// device-service .setup/docker-compose.yml), so this only covers the ones
// actually configured in this repo; an unrecognised key just shows its raw
// name, same as an unrecognised label would.
export const MODEL_NAMES = {
  default: { fr: 'par défaut', ar: 'افتراضي', zh: '默认' },
  fire: { fr: 'feu', ar: 'حريق', zh: '火' },
  plant: { fr: 'plante', ar: 'نبات', zh: '植物' },
}

export function labelText(raw, loc) {
  if (!raw) return raw
  const entry = LABELS_LC[raw.toLowerCase()]
  return (entry && entry[loc]) || raw
}

// A running task's model can be "default,fire,plant" - every currently
// available model joined by commas, not just two - so this must translate
// each part and rejoin, not look up the whole string as one key.
const JOINERS = { ar: '، ' }

export function modelText(raw, loc) {
  if (!raw) return raw
  const sep = JOINERS[loc] || ', '
  return raw
    .split(',')
    .map((name) => (MODEL_NAMES[name] && MODEL_NAMES[name][loc]) || name)
    .join(sep)
}
