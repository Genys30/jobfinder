/**
 * Synonym groups for Israeli tech + public-sector job search.
 * Each group: aliases are equivalent (OR). Query must hit any needle in the group.
 * Loaded after normalize.js; used by query.js.
 */
(function (global) {
  const { normalizeSearchText, compactSearchText } = global.SearchNormalize;

  /** @type {string[][]} token/role groups */
  const GROUPS = [
    // ── Engineering ─────────────────────────────────────────────────────────
    ['frontend', 'front-end', 'front end', 'front end developer', 'front-end developer',
      'frontend developer', 'frontend engineer', 'front end engineer', 'ui developer',
      'פרונט', 'פרונט אנד', 'פיתוח פרונט', 'מפתח פרונט', 'מפתח/ת פרונט', 'מפתחת פרונט',
      'מפתח פרונט אנד', 'מפתח/ת פרונט אנד', 'מפתחת פרונט אנד'],
    ['backend', 'back-end', 'back end', 'back end developer', 'backend developer',
      'backend engineer', 'server side', 'server-side', 'צד שרת', 'מפתח backend',
      'מפתח/ת backend', 'מהנדס/ת backend', 'מהנדס backend'],
    ['full stack', 'fullstack', 'full-stack', 'full stack developer', 'fullstack developer',
      'פול סטאק', 'פולסטאק', 'מפתח/ת פול סטאק'],
    ['software engineer', 'software developer', 'developer', 'engineer', 'sw engineer',
      'מפתח', 'מפתח/ת', 'מפתחת', 'מהנדס', 'מהנדס/ת', 'מהנדסת', 'מהנדס תוכנה',
      'מפתח תוכנה', 'מפתח/ת תוכנה', 'מהנדס/ת תוכנה'],
    ['devops', 'dev ops', 'dev-ops', 'devsecops', 'platform engineer', 'infrastructure engineer',
      'דבאופס', 'דב ops', 'מהנדס/ת תשתיות', 'מהנדס תשתיות', 'פלטפורמה'],
    ['sre', 'site reliability', 'site reliability engineer', 'reliability engineer',
      'production engineer', 'מהנדס/ת ייצוב'],
    ['qa', 'quality assurance', 'software tester', 'software test engineer', 'test engineer',
      'sdet', 'automation engineer', 'qa engineer', 'מבטח/ת איכות', 'מבטח איכות',
      'בדיקות תוכנה', 'בודק/ת תוכנה', 'בודק תוכנה', 'מהנדס/ת בדיקות'],
    ['security', 'cyber', 'cybersecurity', 'cyber security', 'information security',
      'appsec', 'application security', 'infosec', 'אבטחת מידע', 'אבטחת סייבר', 'סייבר',
      'מומחה/ית אבטחה', 'מהנדס/ת אבטחה'],
    ['architect', 'software architect', 'solution architect', 'system architect',
      'systems architect', 'technical architect', 'ארכיטקט', 'ארכיטקט/ית', 'ארכיטקט תוכנה'],
    ['mobile', 'mobile developer', 'mobile engineer', 'ios', 'ios developer', 'android',
      'android developer', 'flutter', 'react native', 'מובייל', 'מפתח/ת מובייל',
      'מהנדס/ת מובייל'],
    ['embedded', 'firmware', 'embedded software', 'embedded engineer', 'firmware engineer',
      'משובץ', 'קושחה', 'מהנדס/ת משובץ'],
    ['hardware', 'electrical engineer', 'electronics', 'vlsi', 'chip', 'מהנדס/ת חומרה',
      'מהנדס חומרה'],
    ['network', 'network engineer', 'network administrator', 'מהנדס/ת רשת', 'רשתות'],
    ['dba', 'database administrator', 'database engineer', 'db administrator',
      'מנהל/ת בסיסי נתונים', 'בסיסי נתונים'],
    ['it', 'information technology', 'system administrator', 'sysadmin', 'it administrator',
      'it support', 'helpdesk', 'תמיכה טכנית', 'איש/אשת סיסטם', 'מנהל/ת מערכות מידע'],

    // ── Data & AI ───────────────────────────────────────────────────────────
    ['data scientist', 'data science', 'מדען/ית נתונים', 'מדען נתונים', 'מדענית נתונים',
      'machine learning', 'ml'],
    ['data engineer', 'data engineering', 'מהנדס/ת דאטה', 'מהנדס דאטה', 'מהנדס/ת נתונים'],
    ['data analyst', 'data analysis', 'business analyst', 'analytics', 'אנליסט/ית',
      'אנליסט', 'אנליסטית', 'אנליסט/ית נתונים', 'אנליטיקה'],
    ['machine learning', 'ml engineer', 'ml', 'deep learning', 'ai engineer',
      'artificial intelligence', 'ai', 'llm', 'nlp', 'computer vision',
      'data scientist', 'data science', 'מדען/ית נתונים', 'מדען נתונים',
      'למידת מחשב', 'בינה מלאכותית', 'מידענות', 'מפתח/ת ai'],
    ['bi', 'business intelligence', 'bi developer', 'bi analyst', 'דוחות'],

    // ── Product & Project ─────────────────────────────────────────────────────
    ['product manager', 'product owner', 'product lead', 'product management', 'pm', 'po',
      'מנהל/ת מוצר', 'מנהל מוצר', 'מנהלת מוצר', 'בעל/ת מוצר', 'בעל מוצר'],
    ['project manager', 'program manager', 'project management', 'scrum master',
      'agile coach', 'מנהל/ת פרויקט', 'מנהל פרויקט', 'רכז/ת פרויקטים'],
    ['business analyst', 'ba', 'systems analyst', 'אנליסט/ית עסקי', 'אנליסט עסקי',
      'אנליסט/ית', 'אנליסט'],

    // ── Design ────────────────────────────────────────────────────────────────
    ['ux', 'ui', 'ux designer', 'ui designer', 'ui/ux', 'ux/ui', 'product designer',
      'user experience', 'user interface', 'interaction designer', 'מעצב/ת', 'מעצב',
      'מעצבת', 'מעצב/ת ux', 'מעצב/ת ui', 'מעצב/ת מוצר'],

    // ── Business & GTM ──────────────────────────────────────────────────────
    ['sales', 'account executive', 'account manager', 'sales manager', 'sales engineer',
      'business development', 'bdr', 'sdr', 'מכירות', 'מנהל/ת מכירות', 'נציג/ת מכירות',
      'פיתוח עסקי', 'רכז/ת מכירות'],
    ['marketing', 'growth', 'demand generation', 'digital marketing', 'content marketing',
      'product marketing', 'שיווק', 'מנהל/ת שיווק', 'גיוס לידים'],
    ['customer success', 'client success', 'customer support', 'technical support',
      'support engineer', 'שירות לקוחות', 'הצלחת לקוחות', 'תמיכה'],
    ['operations', 'biz ops', 'revenue ops', 'sales ops', 'ops manager', 'תפעול',
      'מנהל/ת תפעול'],

    // ── HR & People ─────────────────────────────────────────────────────────
    ['hr', 'human resources', 'people operations', 'people ops', 'hrbp',
      'hr business partner', 'talent acquisition', 'talent partner', 'recruiter',
      'recruiting', 'recruitment', 'משאבי אנוש', 'גיוס', 'מגייס/ת', 'מגייס',
      'מגייסת', 'רכז/ת גיוס', 'שותף/ת משאבי אנוש'],

    // ── Finance & Legal ───────────────────────────────────────────────────────
    ['finance', 'financial analyst', 'controller', 'fp&a', 'accountant', 'cpa',
      'כספים', 'כלכלן/ית', 'חשב/ת', 'רואה חשבון', 'חשבונאות'],
    ['legal', 'counsel', 'lawyer', 'attorney', 'compliance', 'משפטן/ית', 'משפטית',
      'עורך/ת דין', 'רגולציה'],

    // ── Level (common query terms) ────────────────────────────────────────────
    ['junior', 'jr', 'entry level', 'entry-level', 'graduate', 'new grad', 'fresher',
      'trainee', 'מתחיל/ה', 'זוטר/ה', 'ג\'וניור'],
    ['senior', 'sr', 'experienced', 'בכיר/ה', 'בכיר', 'בכירה'],
    ['intern', 'internship', 'student', 'co-op', 'coop', 'סטודנט/ית', 'סטודנט',
      'מתמחה/ה', 'מתמחה', 'התמחות'],
    ['director', 'head of', 'vp', 'vice president', 'chief', 'cto', 'ceo', 'cfo',
      'cmo', 'cpo', 'מנהל/ת', 'מנהל', 'מנהלת', 'ראש', 'סמנכ"ל', 'מנכ"ל'],

    // ── Work model ────────────────────────────────────────────────────────────
    ['remote', 'work from home', 'wfh', 'מהבית', 'עבודה מהבית', 'מרחוק'],
    ['hybrid', 'היברידי', 'היברידית'],

    // ── Stacks (common search terms) ──────────────────────────────────────────
    ['javascript', 'js', 'typescript', 'ts', 'ecmascript'],
    ['react', 'reactjs', 'react.js'],
    ['node', 'nodejs', 'node.js'],
    ['python', 'django', 'flask'],
    ['java', 'spring', 'spring boot'],
    ['csharp', 'c#', '.net', 'dotnet', 'asp.net'],
    ['golang', 'go lang', 'go developer'],
    ['aws', 'amazon web services', 'cloud engineer'],
    ['kubernetes', 'k8s', 'kube'],
    ['sql', 'postgres', 'postgresql', 'mysql'],

    // ── Israeli public sector & institutions ──────────────────────────────────
    ['government', 'public sector', 'civil service', 'ממשלה', 'ממשלתי', 'מגזר ציבורי',
      'שירות המדינה', 'אזרחי', 'משרה ממשלתית', 'משרד ממשלתי'],
    ['defense', 'defence', 'military', 'idf', 'ביטחון', 'הגנה', 'ביטחוני', 'צבא',
      'צה"ל', 'משרד הביטחון', 'מערכת הביטחון'],
    ['nonprofit', 'non-profit', 'ngo', 'third sector', 'מגזר שלישי', 'עמותה',
      'ארגון חברתי', 'לא ממשלתי'],
    ['hospital', 'medical center', 'health fund', 'clalit', 'מוסד רפואי', 'בית חולים',
      'מרכז רפואי', 'קופת חולים', 'רפואה', 'בריאות'],
    ['university', 'academic', 'research', 'אוניברסיטה', 'אקדמי', 'אקדמיה', 'מחקר',
      'מכון מחקר', 'הוראה', 'מרצה'],
    ['teacher', 'teaching', 'education', 'מורה', 'הוראה', 'חינוך', 'גננת', 'מחנך'],
    ['social worker', 'עובד/ת סוציאלי', 'סוציאלי', 'רווחה'],
    ['administrative', 'administration', 'office manager', 'executive assistant',
      'מנהל/ת משרד', 'אדמיניסטרציה', 'מזכיר/ה', 'מזכירה', 'סייע/ת אדמיניסטרטיבי'],
    ['nurse', 'nursing', 'אח/ות', 'אחות', 'אח', 'סיעוד'],
    ['procurement', 'purchasing', 'רכש', 'קניין'],
  ];

  /** Short tokens: expand only on exact query; match uses word boundaries (see hayMatchesAny). */
  const EXACT_ONLY = new Set(['ba', 'qa', 'ui', 'ux', 'hr', 'bd', 'ae', 'vp', 'js', 'ts', 'go', 'pm', 'po']);

  let groupByCompact = null;

  function buildIndex() {
    if (groupByCompact) return;
    groupByCompact = new Map();
    for (const group of GROUPS) {
      const needles = new Set();
      for (const alias of group) {
        const c = compactSearchText(alias);
        if (c.length >= 2) needles.add(c);
      }
      if (!needles.size) continue;
      for (const alias of group) {
        const c = compactSearchText(alias);
        if (c.length >= 2) groupByCompact.set(c, needles);
      }
    }
  }

  function needlesForCompact(compact, exactOnly) {
    buildIndex();
    if (!compact || compact.length < 2) return [];
    if (EXACT_ONLY.has(compact) && !exactOnly) {
      return [compact];
    }
    const group = groupByCompact.get(compact);
    if (group) return [...group];
    return [compact];
  }

  function needlesForToken(token) {
    const norm = normalizeSearchText(token);
    const compact = compactSearchText(norm);
    return needlesForCompact(compact, true);
  }

  function needlesForPhrase(normalizedQuery) {
    const compact = compactSearchText(normalizedQuery);
    const out = new Set();
    needlesForCompact(compact, true).forEach(function (n) {
      out.add(n);
    });
    const norm = normalizeSearchText(normalizedQuery);
    for (const group of GROUPS) {
      for (const alias of group) {
        if (normalizeSearchText(alias) === norm) {
          group.forEach(function (a) {
            const c = compactSearchText(a);
            if (c.length >= 2) out.add(c);
          });
          break;
        }
      }
    }
    return [...out];
  }

  /** Needles shorter than this use token Set only (no compact substring). */
  const COMPACT_FALLBACK_MIN = 6;

  function escapeRe(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /**
   * @param {{ norm: string, compact: string, tokens?: Set<string> }} field
   */
  function needleMatchesField(field, needle) {
    if (!field || !needle || needle.length < 2) return false;

    if (needle.length <= 3 && field.norm) {
      const re = new RegExp('(?:^|[\\s/])' + escapeRe(needle) + '(?:$|[\\s/])', 'i');
      return re.test(field.norm);
    }

    if (field.tokens && field.tokens.has(needle)) return true;

    if (needle.length < COMPACT_FALLBACK_MIN) return false;

    return field.compact.includes(needle);
  }

  function needleMatches(job, needle) {
    return needleMatchesField(
      {
        norm: job._searchNorm || '',
        compact: job._searchCompact || '',
        tokens: job._searchTokenSet,
      },
      needle
    );
  }

  function hayMatchesAny(job, needles) {
    for (let i = 0; i < needles.length; i++) {
      if (needleMatches(job, needles[i])) return true;
    }
    return false;
  }

  global.SearchSynonyms = {
    GROUPS,
    needlesForToken,
    needlesForPhrase,
    hayMatchesAny,
    needleMatches,
    needleMatchesField,
    MIN_TOKEN_LEN: 4,
    COMPACT_FALLBACK_MIN,
  };
})(typeof window !== 'undefined' ? window : global);
