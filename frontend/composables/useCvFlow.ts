import { ref, computed } from 'vue'

type JobMatch = {
    id: string
    title: string
    company: string
    location?: string
    url?: string
    matchPct?: number
    job_type?: string
    is_remote?: boolean
    salary_text?: string
    site?: string
    date_posted?: string
}

class HttpError extends Error {
    status: number
    data: any
    constructor(status: number, data: any, fallback = 'Request failed') {
        const detail =
            typeof data?.detail === 'string'
                ? data.detail
                : Array.isArray(data?.detail)
                    ? JSON.stringify(data.detail)
                    : data?.message || fallback
        super(detail)
        this.status = status
        this.data = data
    }
}

async function fetchJSON(url: string, init?: RequestInit) {
    const resp = await fetch(url, init)
    let data: any = null
    try { data = await resp.json() } catch {}
    if (!resp.ok) throw new HttpError(resp.status, data)
    return data
}

function salaryText(j: any) {
    const fmt = (n: number) =>
        n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M`
            : n >= 1_000 ? `${(n / 1_000).toFixed(0)}K`
                : String(n || '')
    const min = j.salary_min ? fmt(j.salary_min) : ''
    const max = j.salary_max ? fmt(j.salary_max) : ''
    const interval = j.interval || 'yearly'
    return min || max ? `${min}${min && max ? ' - ' : ''}${max} (${interval})` : ''
}

function cryptoRandomId() {
    if (typeof crypto !== 'undefined' && 'getRandomValues' in crypto) {
        const buf = new Uint32Array(2)
        crypto.getRandomValues(buf)
        return Array.from(buf, (n) => n.toString(36)).join('')
    }
    return Math.random().toString(36).slice(2)
}

const csv = (s?: string) => (s || '').split(',').map(v => v.trim()).filter(Boolean)

const DEFAULT_LOCATION = 'Indonesia'
const DEFAULT_SITES = ['linkedin', 'indeed']
const RESULTS_WANTED = 20
export const allSites = ['linkedin', 'indeed', 'glassdoor', 'jobstreet']

let singleton: ReturnType<typeof createStore> | null = null

function createStore() {
    // ---------- CV / hasil ----------
    const fileInputRef = ref<HTMLInputElement | null>(null)
    const file = ref<File | null>(null)
    const fileName = ref('')
    const hasFile = computed(() => !!file.value)

    const loading = ref(false)
    const statusMsg = ref('')
    const result = ref<any | null>(null)
    const matches = ref<JobMatch[]>([])

    // ---------- opsi pencarian ----------
    const optionsOpen = ref(false)
    const optLocation = ref<string>(DEFAULT_LOCATION)
    const optCustomLocation = ref('')
    const optSites = ref<string[]>([...DEFAULT_SITES])
    const optResultsWanted = ref<number>(RESULTS_WANTED)
    const optEnableMatching = ref(false)
    const optIncludeScam = ref(true)
    const optLanguage = ref<'en' | 'id'>('en')
    const optTopMatches = ref<number>(10)

    const locationParam = computed(() =>
        optLocation.value === 'custom'
            ? (optCustomLocation.value.trim() || DEFAULT_LOCATION)
            : optLocation.value
    )

    // ---------- modal hasil (mobile) ----------
    const modalOpen = ref(false)
    const modalTab = ref<'cv' | 'jobs'>('cv')

    // ---------- subscription ----------
    const subscriptionOpen = ref(false)
    const subStep = ref<'offer' | 'review' | 'edit'>('offer')
    const subEmail = ref('')

    const inferredTitle = ref('') // hasil infer
    const subPosition = ref('')   // editable (final_role)
    const subSeniority = ref<'intern'|'junior'|'mid'|'senior'|'lead'>('junior')

    const subMustSkills = ref('')
    const subNiceSkills = ref('')
    const subExcludeKeywords = ref('')
    const subExcludeCompanies = ref('')
    const subJobTypes = ref<Array<'fulltime'|'parttime'|'contract'|'internship'>>(['fulltime'])
    const subRemoteType = ref<'onsite'|'hybrid'|'remote'>('onsite')
    const subSalaryMin = ref(0)
    const subSalaryCurrency = ref<'IDR'|'USD'|'SGD'|'EUR'>('IDR')
    const subFrequency = ref<'daily'|'weekly'|'monthly'>('weekly')
    const subTopN = ref(10)
    const subAlertThreshold = ref(0.6)

    const subLocation = ref<string>(DEFAULT_LOCATION)
    const subCustomLocation = ref('')
    const subSites = ref<string[]>([...DEFAULT_SITES])
    const subLanguage = ref<'en' | 'id'>('en')
    const subTopMatches = ref(10)
    const subResultsWanted = ref(RESULTS_WANTED)
    const subEnableMatching = ref(false)
    const subIncludeScam = ref(true)

    const subLocationParam = computed(() =>
        subLocation.value === 'custom'
            ? (subCustomLocation.value.trim() || DEFAULT_LOCATION)
            : subLocation.value
    )

    const subSubmitting = ref(false)
    const subError = ref('')

    // ---------- actions ----------
    function openOptions() {
        optionsOpen.value = true
        if (typeof document !== 'undefined') document.documentElement.style.overflow = 'hidden'
    }
    function closeOptions() {
        optionsOpen.value = false
        if (typeof document !== 'undefined') document.documentElement.style.overflow = ''
    }
    function applyOptions() { closeOptions() }

    function openModal(tab: 'cv' | 'jobs') {
        modalTab.value = tab
        modalOpen.value = true
        if (typeof document !== 'undefined') document.documentElement.style.overflow = 'hidden'
    }
    function closeModal() {
        modalOpen.value = false
        if (typeof document !== 'undefined') document.documentElement.style.overflow = ''
    }

    function primeSubscriptionFromOptions() {
        subLocation.value = optLocation.value
        subCustomLocation.value = optCustomLocation.value
        subSites.value = [...optSites.value]
        subLanguage.value = optLanguage.value
        subTopMatches.value = optTopMatches.value
        subResultsWanted.value = optResultsWanted.value
        subEnableMatching.value = optEnableMatching.value
        subIncludeScam.value = optIncludeScam.value
    }
    function openSubscription() {
        subStep.value = 'offer'
        subscriptionOpen.value = true
        if (typeof document !== 'undefined') document.documentElement.style.overflow = 'hidden'
    }
    function closeSubscription() {
        subscriptionOpen.value = false
        if (typeof document !== 'undefined') document.documentElement.style.overflow = ''
        subSubmitting.value = false
        subError.value = ''
    }
    function goReview() {
        subStep.value = 'review'
    }

    function onFileChange(e: Event) {
        const t = e.target as HTMLInputElement
        file.value = t.files?.[0] ?? null
        fileName.value = file.value?.name ?? ''
    }

    // ---------- API: CV ----------
    async function inferPosition(profile: any) {
        const body = { cv_profile: profile, top_alternates: 2, allow_freshgrad_bias: true, language: 'en' }
        return await fetchJSON(`/api/cv/infer-position`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
    }

    async function smartDiscovery(opts: {
        cv_profile: any
        position_inference: any
        location: string
        sites: string[]
        resultsWanted: number
        enable_matching: boolean
        include_scam_check: boolean
        language: string
        top_matches: number
    }) {
        const params = new URLSearchParams()
        if (opts.location) params.set('location', opts.location)
        params.set('results_wanted', String(opts.resultsWanted))
        params.set('top_matches', String(opts.top_matches ?? 10))
        params.set('include_scam_check', String(!!opts.include_scam_check))
        params.set('enable_matching', String(!!opts.enable_matching))
        if (opts.language) params.set('language', opts.language)
        ;(opts.sites || []).forEach(s => s && params.append('sites', s))

        const body = { cv_profile: opts.cv_profile, position_inference: opts.position_inference }

        return await fetchJSON(`/api/jobs/smart-discovery?${params.toString()}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
    }

    function normalizeSmartDiscovery(payload: any): JobMatch[] {
        const arr = payload?.matches ?? []
        return arr
            .map((m: any) => {
                const j = m?.job
                if (!j) return null
                return {
                    id: j.job_id || j.job_url || cryptoRandomId(),
                    title: j.title,
                    company: j.company,
                    location: j.location,
                    url: j.job_url,
                    matchPct: Math.round(m.match_percentage ?? 0),
                    job_type: j.job_type,
                    is_remote: j.is_remote,
                    salary_text: salaryText(j),
                    site: j.site,
                    date_posted: j.date_posted
                } as JobMatch
            })
            .filter(Boolean) as JobMatch[]
    }

    // ---------- API: Subscription ----------
    async function subscribeJobAlerts() {
        const payload = {
            email: subEmail.value,
            user_name: result.value?.profile?.name || '',
            preferences: {
                final_role: subPosition.value || inferredTitle.value || '',
                seniority: subSeniority.value,
                must_have_skills: csv(subMustSkills.value),
                nice_to_have_skills: csv(subNiceSkills.value),
                exclude_keywords: csv(subExcludeKeywords.value),
                exclude_companies: csv(subExcludeCompanies.value),
                locations: [subLocationParam.value],
                sites: subSites.value,
                job_types: subJobTypes.value,
                remote_type: subRemoteType.value,
                salary_min: Number(subSalaryMin.value) || 0,
                salary_currency: subSalaryCurrency.value
            },
            frequency: subFrequency.value,
            top_n: Number(subTopN.value) || 10,
            alert_threshold: Number(subAlertThreshold.value) || 0.6,
            enable_matching: !!subEnableMatching.value,
            enable_scam_check: !!subIncludeScam.value
        }

        const tryPost = async (path: string) =>
            await fetchJSON(path, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })

        const candidates = [
            '/api/subscription',
            '/api/subscription/',
            '/api/subscriptions',
            '/api/subscriptions/'
        ]
        let lastErr: any = null
        for (const p of candidates) {
            try { return await tryPost(p) } catch (e) { lastErr = e }
        }
        throw lastErr
    }

    // ---------- API: Mailry send ----------
    async function sendMailry(payload: {
        to: string
        subject: string
        text?: string
        html?: string
        attachments?: Array<Record<string, any>>
    }) {
        const tryPost = async (path: string) =>
            await fetchJSON(path, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
        const candidates = ['/api/mailry/send', '/api/mailry/send/']
        let lastErr: any = null
        for (const p of candidates) {
            try { return await tryPost(p) } catch (e) { lastErr = e }
        }
        throw lastErr
    }

    function buildWelcomeEmail() {
        const role = subPosition.value || inferredTitle.value || 'your target role'
        const loc = subLocationParam.value
        const freq = subFrequency.value
        const subject = 'Welcome to LokerKerja Job Alerts!'
        const text = `Welcome to LokerKerja! You're now subscribed to ${freq} job alerts for ${role} positions in ${loc}.`
        const html = `<html><body><h1>Welcome to LokerKerja!</h1><p>You're now subscribed to <b>${freq}</b> job alerts for <b>${role}</b> positions in <b>${loc}</b>.</p></body></html>`
        return { subject, text, html }
    }

    async function confirmSubscription() {
        subSubmitting.value = true
        subError.value = ''
        try {
            // 1) Simpan preferensi subscription
            await subscribeJobAlerts()

            // 2) Kirim email sambutan via Mailry
            const { subject, text, html } = buildWelcomeEmail()
            try {
                await sendMailry({
                    to: subEmail.value,
                    subject,
                    text,
                    html,
                    attachments: [] // siapkan jika nanti perlu melampirkan file
                })
                statusMsg.value = 'Subscribed to job alerts ✔ Welcome email sent.'
            } catch (mailErr: any) {
                console.error('[Mailry send error]', mailErr?.data || mailErr)
                statusMsg.value = 'Subscribed to job alerts ✔ (email send failed)'
            }

            // 3) Tutup modal
            subStep.value = 'offer'
            closeSubscription()
        } catch (err: any) {
            console.error('[Subscription error]', err?.data || err)
            subError.value = err instanceof HttpError
                ? `(${err.status}) ${err.message || JSON.stringify(err.data)}`
                : (err?.message || String(err))
        } finally {
            subSubmitting.value = false
        }
    }

    // ---------- Flow utama ----------
    async function onSubmit() {
        if (!file.value) {
            statusMsg.value = 'Please select a CV file first.'
            return
        }
        loading.value = true
        statusMsg.value = 'Analyzing your CV with AI…'
        result.value = null
        matches.value = []

        try {
            // 1) Parse CV
            const fd = new FormData()
            fd.append('file', file.value)
            fd.append('use_cache', 'true')
            const data = await fetchJSON(`/api/cv/parse`, { method: 'POST', body: fd })
            result.value = data

            // 2) Infer position
            statusMsg.value = 'Inferring best position…'
            const pos = await inferPosition(data.profile)
            inferredTitle.value =
                pos?.best_title || pos?.title || pos?.position || data?.profile?.headline || data?.profile?.title || ''
            if (!subPosition.value) subPosition.value = inferredTitle.value || ''

            // 3) Discover jobs (pakai opsi)
            statusMsg.value = 'Finding job matches…'
            const discovery = await smartDiscovery({
                cv_profile: data.profile,
                position_inference: pos,
                location: locationParam.value,
                sites: optSites.value.length ? optSites.value : DEFAULT_SITES,
                resultsWanted: optResultsWanted.value || RESULTS_WANTED,
                enable_matching: optEnableMatching.value,
                include_scam_check: optIncludeScam.value,
                language: optLanguage.value,
                top_matches: optTopMatches.value || 10
            })

            matches.value = normalizeSmartDiscovery(discovery)
            statusMsg.value = `Found ${matches.value.length} matches ✔`

            // 4) Offer subscription – SATU KALI
            primeSubscriptionFromOptions()
            openSubscription()
        } catch (err: any) {
            console.error('[CV flow error]', err?.data || err)
            const msg = err instanceof HttpError
                ? `(${err.status}) ${err.message || 'Unknown error'}`
                : (err?.message || String(err))
            statusMsg.value = 'CV analysis failed: ' + msg
        } finally {
            loading.value = false
        }
    }

    function clearAll() {
        loading.value = false
        statusMsg.value = ''
        result.value = null
        matches.value = []
        file.value = null
        fileName.value = ''
        if (fileInputRef.value) fileInputRef.value.value = ''
        if (modalOpen.value) closeModal()
        if (optionsOpen.value) closeOptions()
        if (subscriptionOpen.value) closeSubscription()
        modalTab.value = 'cv'
        if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('cv:cleared'))
    }

    return {
        // state
        fileInputRef, file, fileName, hasFile,
        loading, statusMsg, result, matches,

        // options
        optionsOpen, optLocation, optCustomLocation, optSites, optResultsWanted,
        optEnableMatching, optIncludeScam, optLanguage, optTopMatches, locationParam,

        // modals
        modalOpen, modalTab, subscriptionOpen, subStep,

        // subscription fields
        subEmail, inferredTitle, subPosition, subSeniority,
        subMustSkills, subNiceSkills, subExcludeKeywords, subExcludeCompanies,
        subJobTypes, subRemoteType, subSalaryMin, subSalaryCurrency,
        subFrequency, subTopN, subAlertThreshold,
        subLocation, subCustomLocation, subSites, subLanguage,
        subTopMatches, subResultsWanted, subEnableMatching, subIncludeScam,
        subLocationParam, subSubmitting, subError,

        // actions
        onFileChange, onSubmit, clearAll,
        openOptions, closeOptions, applyOptions,
        openModal, closeModal,
        openSubscription, closeSubscription, goReview, confirmSubscription,
    }
}

export function useCvFlow() {
    if (singleton) return singleton
    singleton = createStore()
    return singleton
}

