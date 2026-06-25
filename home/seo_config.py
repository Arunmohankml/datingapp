"""
Centralized SEO content for KnotSpot marketing and campus landing pages.
"""

BASE_URL = "https://knotspot.online"

# Shared FAQ items shown on all SEO pages (plus page-specific extras)
COMMON_FAQ = [
    {
        "question": "How do I connect with students on KnotSpot?",
        "answer": (
            "Sign in with your Google account, complete your profile, and take the personality quiz. "
            "KnotSpot uses your interests and quiz answers to suggest compatible students on your campus "
            "and across supported colleges. You can browse profiles, send match requests, and start chatting "
            "once both sides accept."
        ),
    },
    {
        "question": "Is KnotSpot free?",
        "answer": (
            "Yes. KnotSpot is free for students. There are no subscription fees to use matching, "
            "confessions, roommate finder, events, or communities."
        ),
    },
    {
        "question": "Can students from different colleges connect?",
        "answer": (
            "Yes. While KnotSpot is organized by campus, students from SRM, VIT, Amrita, and other "
            "supported universities can discover and connect with each other when preferences allow."
        ),
    },
    {
        "question": "Can I post anonymous confessions?",
        "answer": (
            "Yes. The confessions feature lets you share thoughts anonymously. Posts are moderated "
            "to remove defamation, vulgarity, and harmful content before they appear publicly."
        ),
    },
    {
        "question": "Is KnotSpot affiliated with any university?",
        "answer": (
            "No. KnotSpot is an independent, student-built platform. It is not officially affiliated "
            "with, endorsed by, or managed by SRM, VIT, Amrita, or any university administration."
        ),
    },
    {
        "question": "Is KnotSpot a profitable platform?",
        "answer": (
            "No. KnotSpot is a passion project built to help students connect. It is not operated "
            "as a profit-driven commercial product."
        ),
    },
    {
        "question": "Who is the developer and founder of KnotSpot?",
        "answer": (
            "KnotSpot was founded and developed by Arun Mohan K, a Computer Science and Engineering "
            "student at SRM Institute of Science and Technology, Ramapuram Campus. He is originally "
            "from Malappuram, Kerala. Instagram: @4ruun"
        ),
    },
    {
        "question": "How are profiles verified?",
        "answer": (
            "KnotSpot uses AI-powered face verification so students can confirm they are real people. "
            "Verified profiles help keep the community safer and reduce fake accounts."
        ),
    },
]

PAGE_FAQ_EXTRA = {
    "student_matching": [
        {
            "question": "How does personality quiz based matching work?",
            "answer": (
                "After onboarding, you answer a short personality and interest quiz. KnotSpot compares "
                "your responses with other students to surface people with similar vibes, hobbies, and "
                "social preferences — making it easier to start genuine friendships."
            ),
        },
    ],
    "college_roommate_finder": [
        {
            "question": "How do I find roommates on KnotSpot?",
            "answer": (
                "Open Roomie (Room Finder), filter by campus, budget, and accommodation type, then browse "
                "listings or post your own. You can also respond to room requests from students looking "
                "for flatmates, PG mates, or shared hostel rooms."
            ),
        },
    ],
    "anonymous_campus_confessions": [
        {
            "question": "Are confessions really anonymous?",
            "answer": (
                "Yes. Your identity is not shown on confession posts. Moderators review content for safety "
                "without revealing who wrote it."
            ),
        },
    ],
    "campus_events": [
        {
            "question": "Can I advertise my campus event on KnotSpot?",
            "answer": (
                "Yes. Students and clubs can submit events — workshops, fests, club meets, and more — "
                "so peers on the same campus can discover and attend."
            ),
        },
    ],
}


def get_faq_for_page(page_key=None):
    """Return combined FAQ list for a page."""
    faqs = list(COMMON_FAQ)
    if page_key and page_key in PAGE_FAQ_EXTRA:
        faqs.extend(PAGE_FAQ_EXTRA[page_key])
    return faqs


def faq_schema_json(faqs):
    """Build FAQPage schema dict from FAQ list."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item["answer"],
                },
            }
            for item in faqs
        ],
    }


def breadcrumb_schema_json(items):
    """Build BreadcrumbList schema from list of {name, url} dicts."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": item["name"],
                "item": item["url"],
            }
            for i, item in enumerate(items)
        ],
    }


# Internal link cards shown at bottom of feature pages
INTERNAL_LINKS = {
    "campuses": [
        {"title": "Student Matching", "url_name": "seo_student_matching", "desc": "Find friends through interests and personality quizzes."},
        {"title": "Roommate Finder", "url_name": "seo_roommate_finder", "desc": "Browse flats, PGs, and verified student roommates."},
        {"title": "Campus Confessions", "url_name": "seo_confessions", "desc": "Share anonymous campus stories safely."},
        {"title": "Campus Events", "url_name": "seo_campus_events", "desc": "Discover fests, workshops, and club activities."},
    ],
    "student_matching": [
        {"title": "Roommate Finder", "url_name": "seo_roommate_finder", "desc": "Found a match? Find a place to live together."},
        {"title": "Campus Confessions", "url_name": "seo_confessions", "desc": "Join campus conversations anonymously."},
    ],
    "college_roommate_finder": [
        {"title": "Campus Confessions", "url_name": "seo_confessions", "desc": "Housing stress? You're not alone — read campus stories."},
        {"title": "Campus Events", "url_name": "seo_campus_events", "desc": "Meet potential roommates at campus events."},
    ],
    "anonymous_campus_confessions": [
        {"title": "Campus Events", "url_name": "seo_campus_events", "desc": "Turn online energy into real-world meetups."},
        {"title": "All Campuses", "url_name": "seo_campuses", "desc": "Explore SRM, VIT, and Amrita communities."},
    ],
    "campus_events": [
        {"title": "Student Communities", "url_name": "seo_campuses", "desc": "Find your campus hub and connect with peers."},
        {"title": "Student Matching", "url_name": "seo_student_matching", "desc": "Meet people before the next fest."},
    ],
}


FEATURE_PAGES = {
    "campuses": {
        "page_key": "campuses",
        "url_path": "/campuses/",
        "title": "Campuses on KnotSpot | Connect with Students Across India",
        "meta_description": (
            "Explore all KnotSpot campuses — SRM, VIT, and Amrita. Find friends, roommates, "
            "confessions, events, and student communities on India's student social platform."
        ),
        "h1": "Campuses on KnotSpot",
        "subtitle": "One student social platform for SRM, VIT, Amrita, and growing college communities across India.",
        "sections": [
            {
                "heading": "What Is KnotSpot?",
                "paragraphs": [
                    "KnotSpot is a student social platform built for college life. Instead of juggling dozens of WhatsApp groups, Instagram DMs, and random housing brokers, students get one place to make friends, find roommates, share anonymous confessions, discover campus events, and join communities that actually feel like their campus.",
                    "Whether you are a first-year trying to find your people, a senior looking for a flatmate before placement season, or someone who just wants to read what your campus is really thinking — KnotSpot brings those everyday student needs together in a single, moderated environment.",
                    "The platform supports multiple universities while keeping each campus identity intact. You always know which community you are in, but you are not locked inside a bubble — cross-campus discovery is part of the experience when you want it.",
                ],
            },
            {
                "heading": "Supported Universities",
                "paragraphs": [
                    "KnotSpot currently serves students across three major university groups: SRM Institute of Science and Technology, Vellore Institute of Technology (VIT), and Amrita Vishwa Vidyapeetham. Each organization has multiple campuses — from SRM Kattankulathur and Ramapuram to VIT Vellore and Chennai, and Amrita Coimbatore, Kochi, Bengaluru, and beyond.",
                    "Every campus has its own space inside KnotSpot. When you sign up, you select your campus so feeds, confessions, roommate listings, and events stay relevant to where you actually study. As new campuses join, they are added through a centralized configuration — no fragmented micro-sites or duplicate apps.",
                    "Explore dedicated landing pages for SRM, VIT, and Amrita, or drill down into individual campus pages like SRM KTR, VIT Vellore, or Amrita Coimbatore for localized content and links.",
                ],
            },
            {
                "heading": "Why Students Use KnotSpot",
                "paragraphs": [
                    "College is socially overwhelming. Lecture halls give you classmates, not necessarily friends. Hostels and PGs introduce housing uncertainty. Clubs and fests happen, but publicity often never leaves a single Telegram channel. KnotSpot addresses these gaps with features designed around how students actually behave online.",
                    "Students use KnotSpot because it feels built by someone who understands campus culture — not a generic social network trying to monetize attention. Matching is interest-driven. Confessions are anonymous but moderated. Room listings come from real students, not brokers. Events are submitted by the people organizing them.",
                    "The result is a college friend finder and student community hub that complements academic life rather than distracting from it.",
                ],
            },
            {
                "heading": "Friends and Student Matching",
                "paragraphs": [
                    "Making friends in college should not depend on luck or which section you landed in. KnotSpot's matching flow combines profile details with a personality quiz so discovery goes beyond surface-level swiping. You see people who share hobbies, study habits, social energy, and campus context.",
                    "Safe profiles and optional verification help you trust who you are talking to. Cross-campus matching lets you connect with students at other colleges when your preferences allow — useful for inter-college events, hometown friends at different institutes, or simply expanding your circle.",
                    "Learn more on our dedicated student matching page.",
                ],
            },
            {
                "heading": "Roommates and Student Housing",
                "paragraphs": [
                    "Finding a roommate near campus is one of the most stressful parts of student life. KnotSpot's Roomie feature lets you browse and post listings for flats, PGs, shared rooms, and hostel vacancies filtered by campus and budget. Students can also publish room requests — a post that says you need a spot in an existing flat.",
                    "Because listings come from verified students rather than anonymous brokers, conversations start with more trust. Whether you need a roommate for SRM Ramapuram, a PG near VIT Vellore, or a shared flat close to Amrita Coimbatore, the roommate finder is built for real student housing needs.",
                ],
            },
            {
                "heading": "Anonymous Campus Confessions",
                "paragraphs": [
                    "Confessions give students a voice without attaching their name. Share campus stories, light-hearted observations, or honest feelings about college life — all anonymously. Every post goes through moderation to block defamation, vulgarity, harassment, and harmful content.",
                    "Confessions are among the most popular entry points to KnotSpot because they capture authentic campus energy. They also connect naturally to other features: someone confessing about a fest might discover the events page; someone looking for a study buddy might jump to matching.",
                ],
            },
            {
                "heading": "Campus Events and Networking",
                "paragraphs": [
                    "Workshops, cultural fests, club meetings, hackathons, and sports trials — campus life runs on events. KnotSpot lets students and organizers advertise what's happening so peers do not miss out. Event listings are campus-aware, making it easy to find what's relevant today.",
                    "Events also support student networking in the simplest sense: showing up. When you know what's on, you meet people outside your usual circle. Combine that with matching and communities, and KnotSpot becomes a practical college networking tool, not just a calendar.",
                ],
            },
            {
                "heading": "Communities, Voice Channels, and More",
                "paragraphs": [
                    "Beyond core feeds, KnotSpot includes student communities, a public drawing wall for creative expression, voice channels for live hangouts, and Spotlight — a way to showcase your Instagram or creator profile to campus peers. These features reinforce KnotSpot as a full student social platform rather than a single-purpose app.",
                    "Each campus page on KnotSpot links to the features most relevant to that location, helping Google and new users understand exactly what is available before they sign in.",
                ],
            },
        ],
    },
    "student_matching": {
        "page_key": "student_matching",
        "url_path": "/student-matching/",
        "title": "Student Matching Platform for College Students | KnotSpot",
        "meta_description": (
            "KnotSpot helps college students find friends through interest-based discovery and "
            "personality quiz matching. Connect safely across SRM, VIT, Amrita campuses."
        ),
        "h1": "Student Matching for College Students",
        "subtitle": "Find friends who share your interests, energy, and campus — powered by personality-aware discovery.",
        "sections": [
            {
                "heading": "A College Friend Finder That Goes Deeper",
                "paragraphs": [
                    "Most social apps treat college students like any other demographic. KnotSpot does not. The student matching experience is designed around how friendships actually form on campus: shared classes, mutual hobbies, compatible personalities, and the occasional cross-branch connection that becomes a lifelong friend.",
                    "Instead of endless random profiles, KnotSpot surfaces students who are more likely to click with you. That makes it a practical college friend finder for first-years who arrive knowing nobody, transfer students adjusting to a new campus, and anyone who wants to expand beyond their existing group.",
                ],
            },
            {
                "heading": "Find Students With Similar Interests",
                "paragraphs": [
                    "Your profile captures what you care about — music, sports, gaming, startups, art, movies, tech, fitness, and more. Matching uses these signals to prioritize people who overlap with your world. When you open the discover feed, you are not scrolling strangers; you are meeting potential friends who already have something to talk about.",
                    "Interest-based discovery reduces awkward cold opens. The first message can reference a shared passion instead of a generic hey. Over time, this creates a student social platform that feels intentional rather than noisy.",
                ],
            },
            {
                "heading": "Personality Quiz Based Matching",
                "paragraphs": [
                    "Interests tell part of the story; personality tells the rest. KnotSpot includes a personality quiz that captures social preferences — how you recharge, how you study, what kind of hangouts you enjoy. Answers are compared with other students to improve compatibility suggestions.",
                    "Quiz-based matching does not label you permanently. It simply helps the platform understand whether you might vibe with someone who loves late-night canteen runs versus someone who prefers quiet library sessions. Students often discover that the best friendships come from complementary personalities, not identical ones — and the quiz helps surface both similarity and balance.",
                    "If you are searching for a student matching app that feels thoughtful rather than gamified, this approach is core to KnotSpot's design.",
                ],
            },
            {
                "heading": "Connect Across Campuses",
                "paragraphs": [
                    "KnotSpot organizes students by campus, but you are not trapped in one location. Cross-campus discovery lets you connect with students at other SRM campuses, across VIT locations, between Amrita centers, or even with friends at entirely different university groups when settings allow.",
                    "This matters for inter-campus events, alumni siblings, hometown connections, and students who simply want a broader network. College networking today is rarely single-campus; KnotSpot reflects that reality while keeping local communities strong.",
                ],
            },
            {
                "heading": "Safe Profiles and Verification",
                "paragraphs": [
                    "Trust is essential when meeting people online. KnotSpot encourages profile verification using AI-powered face checks so users can confirm they are real students. Verified badges help you decide who to connect with, and reporting tools exist for anything that feels off.",
                    "Profiles show enough to start a conversation — campus, interests, photos you choose to share — without exposing sensitive data. The goal is safe discovery, not oversharing.",
                ],
            },
            {
                "heading": "Interest Based Discovery in Practice",
                "paragraphs": [
                    "Discovery is not a one-time onboarding step. As you update interests, answer more quiz questions, and interact on the platform, suggestions adapt. KnotSpot becomes smarter about who you might enjoy meeting next.",
                    "Combine matching with chat, communities, and events, and friendships can move naturally from online intro to real campus hangout. That is the difference between a student matching platform and a passive directory.",
                ],
            },
            {
                "heading": "Building Friendships That Last",
                "paragraphs": [
                    "Matching is only the beginning. KnotSpot gives you chat, voice channels, public drawing walls, and event discovery so connections have room to grow. Many students use matching to find a project partner, gym buddy, confessions reader-turned-friend, or roommate before they ever visit the housing section.",
                    "If you are looking for a student social platform that treats friendship as the goal — not just engagement metrics — KnotSpot's matching feature is the front door.",
                ],
            },
            {
                "heading": "Get Started",
                "paragraphs": [
                    "Sign in with Google, complete your profile, take the quiz, and start browsing students on your campus. Matching is free, student-focused, and built for the realities of college life across SRM, VIT, Amrita, and beyond.",
                ],
            },
        ],
    },
    "college_roommate_finder": {
        "page_key": "college_roommate_finder",
        "url_path": "/college-roommate-finder/",
        "title": "College Roommate Finder | Find Verified Student Roommates | KnotSpot",
        "meta_description": (
            "Find college roommates, flats, PGs, and shared accommodation near SRM, VIT, and Amrita "
            "campuses. Student-posted listings with no brokers on KnotSpot."
        ),
        "h1": "College Roommate Finder for Students",
        "subtitle": "Find flats, PGs, shared rooms, and verified student roommates near your campus.",
        "sections": [
            {
                "heading": "Student Housing Made Simple",
                "paragraphs": [
                    "Every semester, thousands of students search for housing near campus — and most still rely on broker phone numbers forwarded in WhatsApp groups. KnotSpot's Roomie feature is a college roommate finder built specifically for students at SRM, VIT, Amrita, and other supported campuses.",
                    "Browse listings posted by real students, filter by budget and location, or publish your own requirement. Whether you need a full flat, a PG bed, a shared hostel room, or just one person to split rent with, KnotSpot centralizes student housing discovery in one trusted place.",
                ],
            },
            {
                "heading": "Find Roommates, Not Brokers",
                "paragraphs": [
                    "Traditional listing sites mix student posts with commercial agents. KnotSpot focuses on peer-to-peer housing. Listings come from students who study at your campus or nearby, which means conversations start with shared context — same exam schedules, same commute routes, same understanding of what a decent PG actually means.",
                    "The roommate finder supports both sides of the market: people with a room to fill and people looking for a spot. That two-way flow makes it easier to match supply and demand organically.",
                ],
            },
            {
                "heading": "Flats, PGs, and Shared Accommodation",
                "paragraphs": [
                    "Student housing needs vary. Some groups want a full flat near SRM Kattankulathur. Others need an affordable PG walking distance from VIT Vellore. Some Amrita Coimbatore students prefer shared apartments with classmates. KnotSpot listings cover these formats with filters for campus, budget, gender preference where applicable, and accommodation type.",
                    "Detailed posts include location hints, rent splits, amenities, and move-in timelines — the practical details that matter when you are deciding where to live for the next year.",
                ],
            },
            {
                "heading": "Campus Housing Context",
                "paragraphs": [
                    "Housing near one campus is completely different from another. KnotSpot keeps listings campus-aware so you do not waste time on flats on the wrong side of the city. SRM Ramapuram students see Ramapuram-relevant posts; VIT Chennai students see Chennai-area options.",
                    "Campus-specific landing pages link directly into filtered roommate feeds, helping both users and search engines understand geographic relevance.",
                ],
            },
            {
                "heading": "Request to Join a Room",
                "paragraphs": [
                    "Already found a flat but missing one roommate? Post a room request describing the vacancy, rent share, and vibe you want. Students who need a place can respond directly. This request-to-add-you-in-a-room flow mirrors how housing actually gets solved on campus — someone knows someone with a spare bed.",
                    "Room requests complement traditional listings and often convert faster because the group is partially formed already.",
                ],
            },
            {
                "heading": "Safety and Moderation",
                "paragraphs": [
                    "Housing scams target students every year. KnotSpot combines student verification, reporting tools, and moderation to reduce fake listings. While you should always visit a property before paying, starting from a student-only platform significantly lowers risk compared to anonymous classifieds.",
                ],
            },
            {
                "heading": "From Roommate to Friend",
                "paragraphs": [
                    "Many KnotSpot users find roommates through matching first, then search housing together. Others meet via confessions or events and later co-sign a lease. The roommate finder works best as part of the broader student social platform — housing plus community, not housing alone.",
                ],
            },
            {
                "heading": "Start Searching",
                "paragraphs": [
                    "Open the Roomie feed, pick your campus, and browse active listings. Posting is free for students. If you are searching for an SRM roommate finder, VIT roommate finder, or Amrita roommate finder, KnotSpot is built for exactly that.",
                ],
            },
        ],
    },
    "anonymous_campus_confessions": {
        "page_key": "anonymous_campus_confessions",
        "url_path": "/anonymous-campus-confessions/",
        "title": "Anonymous Campus Confessions | KnotSpot",
        "meta_description": (
            "Post anonymous campus confessions on KnotSpot. Moderated student discussions for SRM, "
            "VIT, and Amrita — no defamation, no vulgarity, privacy first."
        ),
        "h1": "Anonymous Campus Confessions",
        "subtitle": "Share campus stories anonymously. Moderated, private, and built for student discussions.",
        "sections": [
            {
                "heading": "A Space for Honest Campus Voices",
                "paragraphs": [
                    "Every campus has thoughts that never make it to Instagram stories — the funny observation about canteen food, the honest feeling about exams, the story you want to tell without your name attached. KnotSpot confessions exist for exactly that kind of expression.",
                    "Anonymous campus confessions have become a defining part of student culture online. KnotSpot brings them into a dedicated, moderated environment rather than scattered across unofficial pages.",
                ],
            },
            {
                "heading": "Anonymous Posting With Real Privacy",
                "paragraphs": [
                    "When you submit a confession, your identity is not displayed publicly. Other students see the content, reactions, and comments — not your profile name. This privacy encourages authentic sharing while community guidelines keep the tone respectful.",
                    "Anonymous posting does not mean consequence-free harassment. KnotSpot actively moderates harmful content.",
                ],
            },
            {
                "heading": "Student Discussions That Feel Like Campus",
                "paragraphs": [
                    "Confessions are filtered by campus so SRM KTR reads differently from VIT Vellore or Amrita Kochi. That localization makes discussions feel relevant — inside jokes, local references, and shared experiences land better when everyone is actually from the same place.",
                    "Comments and reactions turn single posts into conversations. Many students browse confessions daily even if they never post, which makes it a social hub as much as a publishing tool.",
                ],
            },
            {
                "heading": "Campus Stories Without the Drama",
                "paragraphs": [
                    "Confession culture can turn toxic on unmoderated platforms. KnotSpot draws a clear line: share freely, but do not attack individuals, spread rumors, or post explicit content. Campus stories should entertain and connect, not harm.",
                    "Students searching for SRM confessions, VIT confessions, or Amrita confessions will find campus-specific feeds with consistent standards.",
                ],
            },
            {
                "heading": "Fully Moderated — No Defamation, No Vulgarity",
                "paragraphs": [
                    "Every confession passes through moderation before appearing publicly. Posts that include defamation, targeted harassment, hate speech, or vulgarity are rejected. This keeps the feed readable and reduces the legal and personal harm that unmoderated confession pages often create.",
                    "Moderation protects both readers and writers. Anonymous does not give anyone permission to destroy reputations.",
                ],
            },
            {
                "heading": "Privacy by Design",
                "paragraphs": [
                    "KnotSpot minimizes data exposure on confession posts. Your profile is not linked in the feed. Reporting tools let students flag problematic content quickly. Combined with platform-wide community guidelines, privacy and safety are treated as core features — not afterthoughts.",
                ],
            },
            {
                "heading": "Confessions as a Gateway to Community",
                "paragraphs": [
                    "Many students discover KnotSpot through confessions, then explore matching, roommate finder, or events. Confessions answer the question is anyone else feeling this too — and other features answer what can I do about it or who can I meet.",
                ],
            },
            {
                "heading": "Read or Post Today",
                "paragraphs": [
                    "Browse public confessions without an account, or sign in to post and react. Whether you are looking for anonymous campus confessions at SRM Ramapuram, VIT Chennai, or Amrita Bengaluru, KnotSpot has a feed for your campus.",
                ],
            },
        ],
    },
    "campus_events": {
        "page_key": "campus_events",
        "url_path": "/campus-events/",
        "title": "Campus Events for College Students | KnotSpot",
        "meta_description": (
            "Discover and advertise campus events — fests, workshops, clubs, and networking "
            "for SRM, VIT, and Amrita students on KnotSpot."
        ),
        "h1": "Campus Events for Students",
        "subtitle": "Discover fests, workshops, club meets, and advertise your own campus events.",
        "sections": [
            {
                "heading": "Never Miss What's Happening on Campus",
                "paragraphs": [
                    "Campus life moves fast. A workshop announced in one WhatsApp group never reaches the hostel two blocks away. A fest poster gets buried under memes. KnotSpot events centralize what's happening so students can actually show up.",
                    "The events feature is a campus calendar built by students, for students — covering SRM, VIT, Amrita, and every supported campus individually.",
                ],
            },
            {
                "heading": "Fests, Workshops, and Club Activities",
                "paragraphs": [
                    "From cultural fests and hackathons to club auditions and sports trials, events come in every format. KnotSpot listings include titles, dates, campuses, and descriptions so you can decide in seconds whether something is for you.",
                    "Organizers benefit too: instead of spamming ten group chats, they publish once and reach students already browsing KnotSpot for campus content.",
                ],
            },
            {
                "heading": "Advertise Your Campus Events in the App",
                "paragraphs": [
                    "Running an event? Submit it through KnotSpot so it appears in the campus events feed. Clubs, departments, student councils, and informal groups can all promote activities — free workshops, paid concerts, meetups, and networking sessions.",
                    "This makes KnotSpot a practical tool for campus event promotion, not just discovery.",
                ],
            },
            {
                "heading": "Networking Through Real Meetups",
                "paragraphs": [
                    "College networking does not have to mean LinkedIn messages. Showing up to a workshop, joining a club meet, or attending a fest intro session is how most students actually build connections. Events bridge the gap between online discovery and offline friendship.",
                    "Pair events with KnotSpot matching and you have a full loop: discover people online, meet them at an event, continue chatting on the platform.",
                ],
            },
            {
                "heading": "Campus-Specific Listings",
                "paragraphs": [
                    "Events are tagged by campus so VIT Vellore students are not flooded with Amrita Kochi listings unless they choose broader discovery. This campus-aware design improves relevance for users and clarity for search engines trying to understand local student communities.",
                ],
            },
            {
                "heading": "Explore Events Near You",
                "paragraphs": [
                    "Open the events feed, filter by your campus, and see what's coming up. If you organize student activities, submit your next event and reach peers who are already engaged with campus life on KnotSpot.",
                ],
            },
        ],
    },
}


ORG_PAGE_CONTENT = {
    "SRM": {
        "title": "SRM Student Community Platform | KnotSpot",
        "meta_description": (
            "KnotSpot for SRM students — friend finder, roommate discovery, confessions, events, "
            "and communities across KTR, Ramapuram, Vadapalani, and all SRM campuses."
        ),
        "h1": "SRM Student Community Platform",
        "subtitle": "Connect with SRM students across Kattankulathur, Ramapuram, Vadapalani, and every SRM campus on KnotSpot.",
    },
    "VIT": {
        "title": "VIT Student Community Platform | KnotSpot",
        "meta_description": (
            "KnotSpot for VIT students — matching, roommate finder, anonymous confessions, "
            "campus events, and communities at Vellore, Chennai, Bhopal, and more."
        ),
        "h1": "VIT Student Community Platform",
        "subtitle": "The student social hub for VIT Vellore, Chennai, Bhopal, Bangalore, and AP campuses.",
    },
    "Amrita": {
        "title": "Amrita Student Community Platform | KnotSpot",
        "meta_description": (
            "KnotSpot for Amrita students — college friend finder, roommate listings, confessions, "
            "events, and communities across Coimbatore, Kochi, Bengaluru, and all Amrita campuses."
        ),
        "h1": "Amrita Student Community Platform",
        "subtitle": "Connect with Amrita students at Coimbatore, Kochi, Amritapuri, Bengaluru, and every campus.",
    },
}


FOUNDER_PAGE = {
    "title": "Arun Mohan K – Founder of KnotSpot",
    "meta_description": (
        "Meet Arun Mohan K, founder and developer of KnotSpot. CSE student at SRM Ramapuram, "
        "from Malappuram, Kerala — building India's student social platform."
    ),
    "h1": "Arun Mohan K",
    "subtitle": "Founder & Developer, KnotSpot",
    "instagram": "https://www.instagram.com/4ruun/",
    "instagram_handle": "@4ruun",
}
