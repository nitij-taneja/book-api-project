"""
LLM Service for book information extraction and enhancement using Groq.
This service acts as the primary brain for understanding user queries and enriching book data.
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from groq import Groq
from django.conf import settings


class LLMService:
    """Service class for LLM operations using Groq."""

    def __init__(self):
        # Initialize Groq client with version compatibility
        self.client = self._initialize_groq_client()
        # Use faster model for better performance
        self.model = "llama3-8b-8192"  # Keep this model but optimize parameters

    def _initialize_groq_client(self):
        """Initialize Groq client with version compatibility handling."""
        import inspect

        try:
            # Get the Groq constructor signature to check supported parameters
            groq_init_signature = inspect.signature(Groq.__init__)
            supported_params = list(groq_init_signature.parameters.keys())

            # Base parameters that should always work
            init_params = {'api_key': settings.GROQ_API_KEY}

            # Check if this version supports additional parameters we might want to use
            # (This is for future compatibility)

            print(f"Initializing Groq client (supported params: {supported_params})")
            return Groq(**init_params)

        except TypeError as e:
            error_msg = str(e)
            print(f"Groq client initialization failed: {error_msg}")

            if "proxies" in error_msg:
                print("This appears to be a version compatibility issue with the 'proxies' parameter.")
                print("Trying basic initialization...")
                # Fallback to most basic initialization
                return Groq(api_key=settings.GROQ_API_KEY)
            else:
                print(f"Unexpected TypeError during Groq initialization: {error_msg}")
                raise e

        except Exception as e:
            print(f"Error initializing Groq client: {e}")
            print("Please check:")
            print("1. Groq library version (pip show groq)")
            print("2. GROQ_API_KEY environment variable")
            print("3. Network connectivity")
            raise e
    
    def extract_book_info(self, query: str, language: str = 'en') -> Dict:
        """
        Extract structured book information from a user query.
        This is the primary function that makes LLM the first step in book search.
        
        Args:
            query: User's book search query
            language: Target language ('en' or 'ar')
            
        Returns:
            Dict containing extracted book information
        """
        
        # Create language-specific prompt
        if language == 'ar':
            prompt = f"""
            استخرج معلومات الكتاب من الاستعلام التالي: '{query}'

            أجب بتنسيق JSON فقط، مثل هذا:
            {{
                "title": "عنوان الكتاب",
                "author": "اسم المؤلف",
                "categories": ["الفئة الأولى", "الفئة الثانية"],
                "language": "ar",
                "search_variations": ["تنويع البحث 1", "تنويع البحث 2", "تنويع البحث 3"],
                "description": "وصف مختصر للكتاب",
                "is_arabic_query": true
            }}

            متطلبات مهمة:
            - إذا كان الاستعلام يحتوي على كلمات مثل "الاستثمار", "وارن بافيت", "الأسهم" فهذا كتاب عن الاستثمار
            - إذا كان الاستعلام يحتوي على أسماء مؤلفين مشهورين، استخرج الاسم بدقة
            - أنشئ 3-4 تنويعات بحث مختلفة لتحسين نتائج البحث
            - للفئات، استخدم أسماء عربية مثل: "الاستثمار", "المال والأعمال", "التنمية الذاتية", "الأدب", "التاريخ", "العلوم", "الفلسفة", "الدين", "الشعر", "الرواية"
            - إذا لم تكن المعلومات متوفرة، استخدم null

            أمثلة:
            - "الاستثمار في الأسهم على طريقة وارن بافيت" → title: "الاستثمار في الأسهم على طريقة وارن بافيت", author: "وارن بافيت", categories: ["الاستثمار", "المال والأعمال"]
            """
        else:
            prompt = f"""
            Extract book information from the following query: '{query}'
            
            Respond in JSON format only, like this:
            {{
                "title": "Book Title",
                "author": "Author Name", 
                "categories": ["Category1", "Category2"],
                "language": "en",
                "search_variations": ["search variation 1", "search variation 2"],
                "description": "Brief description of the book",
                "is_arabic_query": false
            }}
            
            If information is not available, use null.
            For categories, use common genres like: "Fiction", "History", "Science", "Philosophy", "Religion", "Poetry", "Novel", "Biography"
            Generate 2-3 search variations to improve API search results.
            """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            
            llm_response = chat_completion.choices[0].message.content
            extracted_data = json.loads(llm_response)
            
            # Ensure required fields exist
            extracted_data.setdefault('title', query)
            extracted_data.setdefault('author', None)
            extracted_data.setdefault('categories', [])
            extracted_data.setdefault('language', language)
            extracted_data.setdefault('search_variations', [query])
            extracted_data.setdefault('description', None)
            extracted_data.setdefault('is_arabic_query', language == 'ar')
            
            return extracted_data
            
        except json.JSONDecodeError as e:
            print(f"LLM JSON decode error: {e}")
            return self._fallback_extraction(query, language)
        except Exception as e:
            print(f"LLM extraction error: {e}")
            return self._fallback_extraction(query, language)
    
    def enhance_book_description(self, title: str, author: str, existing_description: str = None, language: str = 'en') -> str:
        """
        Generate or enhance book description using LLM.
        
        Args:
            title: Book title
            author: Book author
            existing_description: Existing description to enhance (optional)
            language: Target language
            
        Returns:
            Enhanced description
        """
        
        if language == 'ar':
            if existing_description:
                prompt = f"""
                حسّن الوصف التالي للكتاب "{title}" للمؤلف "{author}":
                
                الوصف الحالي: {existing_description}
                
                اكتب وصفاً محسناً باللغة العربية (200-300 كلمة) يتضمن:
                - ملخص للمحتوى
                - أهمية الكتاب
                - الجمهور المستهدف
                """
            else:
                prompt = f"""
                اكتب وصفاً شاملاً للكتاب "{title}" للمؤلف "{author}" باللغة العربية.
                
                يجب أن يتضمن الوصف (200-300 كلمة):
                - ملخص للمحتوى الرئيسي
                - أهمية الكتاب وقيمته
                - الجمهور المستهدف
                - السياق التاريخي أو الأدبي إن أمكن
                """
        else:
            if existing_description:
                prompt = f"""
                Enhance the following description for the book "{title}" by "{author}":
                
                Current description: {existing_description}
                
                Write an enhanced description in English (200-300 words) that includes:
                - Content summary
                - Book's significance
                - Target audience
                """
            else:
                prompt = f"""
                Write a concise description for the book "{title}" by "{author}" in English.

                The description should include (100-150 words):
                - Main content summary
                - Book's significance
                - Target audience
                """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                temperature=0.7,
            )
            
            return chat_completion.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"LLM description enhancement error: {e}")
            return existing_description or f"A book titled '{title}' by {author}."
    
    def get_related_books(self, title: str, author: str, categories: List[str], language: str = 'en') -> List[Dict]:
        """
        Generate related book suggestions using LLM.
        
        Args:
            title: Book title
            author: Book author  
            categories: Book categories
            language: Target language
            
        Returns:
            List of related book suggestions
        """
        
        categories_str = ', '.join(categories) if categories else 'General'
        
        if language == 'ar':
            prompt = f"""
            اقترح 5 كتب مشابهة للكتاب "{title}" للمؤلف "{author}" في فئات: {categories_str}
            
            أجب بتنسيق JSON فقط:
            {{
                "related_books": [
                    {{
                        "title": "عنوان الكتاب",
                        "author": "اسم المؤلف",
                        "reason": "سبب التشابه"
                    }}
                ]
            }}
            
            ركز على الكتب العربية أو المترجمة للعربية إن أمكن.
            """
        else:
            prompt = f"""
            Suggest 5 books similar to "{title}" by "{author}" in categories: {categories_str}
            
            Respond in JSON format only:
            {{
                "related_books": [
                    {{
                        "title": "Book Title",
                        "author": "Author Name", 
                        "reason": "Reason for similarity"
                    }}
                ]
            }}
            
            Focus on well-known books in similar genres or themes.
            """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.8,
            )
            
            response = json.loads(chat_completion.choices[0].message.content)
            return response.get('related_books', [])
            
        except Exception as e:
            print(f"LLM related books error: {e}")
            return []
    
    def get_combined_structured_info(self, categories: List[str], author_name: str, book_title: str = "", language: str = 'en') -> Dict:
        """
        Get both structured categories and author info in a single LLM call for better performance.

        Args:
            categories: List of category names
            author_name: Author's name
            book_title: Book title for context
            language: Target language

        Returns:
            Dict containing both categories and author info
        """
        if not categories and not author_name:
            return {"categories": [], "author": {}}

        categories_str = ", ".join(categories) if categories else "Unknown"

        if language == 'ar':
            # Translate categories to Arabic first
            arabic_categories = []
            for cat in categories:
                arabic_translations = {
                    'fiction': 'خيال', 'romance': 'رومانسية', 'history': 'تاريخ',
                    'science': 'علوم', 'philosophy': 'فلسفة', 'poetry': 'شعر',
                    'novel': 'رواية', 'biography': 'سيرة ذاتية', 'mystery': 'غموض',
                    'adventure': 'مغامرة', 'drama': 'دراما', 'comedy': 'كوميديا',
                    'literature': 'أدب', 'courtship': 'خطوبة', 'classic': 'كلاسيكي',
                    'fantasy': 'فانتازيا', 'thriller': 'إثارة', 'horror': 'رعب'
                }
                arabic_cat = arabic_translations.get(cat.lower() if cat else '', cat)
                arabic_categories.append(arabic_cat)

            categories_str_ar = ", ".join(arabic_categories)

            prompt = f"""
            للكتاب "{book_title}" للمؤلف "{author_name}" مع الفئات: {categories_str_ar}

            أنشئ معلومات منظمة باللغة العربية فقط بتنسيق JSON:
            {{
                "categories": [
                    {{
                        "name": "اسم الفئة بالعربية فقط (مثل: خيال، رومانسية، تاريخ)",
                        "icon": "رمز تعبيري مناسب",
                        "wikilink": "https://ar.wikipedia.org/wiki/...",
                        "description": "وصف مفصل للفئة من 60 كلمة عربية بالضبط"
                    }}
                ],
                "author": {{
                    "name": "{author_name}",
                    "image": "https://ui-avatars.com/api/?name={author_name.replace(' ', '+')}&size=300&background=6366f1&color=ffffff&format=png&bold=true",
                    "wikilink": "https://ar.wikipedia.org/wiki/...",
                    "profession": ["كاتب", "روائي", "شاعر"],
                    "descriptions": [
                        "وصف مختصر للمؤلف من 60 كلمة عربية بالضبط يتضمن حياته وأعماله",
                        "معلومات إضافية عن إنجازاته وتأثيره الأدبي"
                    ]
                }},
                "book_summary": "ملخص الكتاب من 100 كلمة عربية بالضبط"
            }}

            قواعد صارمة - يجب اتباعها بدقة:
            - جميع أسماء الفئات يجب أن تكون بالعربية فقط (خيال، رومانسية، تاريخ، أدب، شعر، إلخ)
            - جميع الأوصاف والنصوص يجب أن تكون بالعربية الفصحى فقط
            - لا تستخدم أي كلمات إنجليزية أو لاتينية في أي مكان
            - ترجم أي مصطلحات إنجليزية إلى العربية
            - استخدم روابط ويكيبيديا عربية حقيقية
            - الأوصاف يجب أن تكون بالعدد المحدد من الكلمات العربية
            """

        else:
            prompt = f"""
            For the book "{book_title}" by "{author_name}" with categories: {categories_str}

            Create structured information in JSON format (ALL IN ENGLISH):
            {{
                "categories": [
                    {{
                        "name": "Category Name in English",
                        "icon": "📚",
                        "wikilink": "https://en.wikipedia.org/wiki/...",
                        "description": "Write exactly 60 English words describing this category. Include definition, characteristics, importance, and examples. Make it detailed and informative for readers interested in this literary genre."
                    }}
                ],
                "author": {{
                    "name": "{author_name}",
                    "image": "real author image URL or placeholder",
                    "wikilink": "https://en.wikipedia.org/wiki/...",
                    "profession": ["Writer", "Novelist", "Poet"],
                    "descriptions": [
                        "Write exactly 60 English words describing this author's life, major works, and literary achievements",
                        "Additional information about their writing style, impact on literature, and significance"
                    ]
                }},
                "book_summary": "Write exactly 100 English words summarizing this book. Include the main plot, characters, themes, literary significance, and why it's important. Make it detailed and engaging."
            }}

            CRITICAL REQUIREMENTS - Follow these rules exactly:
            - ALL text must be in English only
            - Category description: EXACTLY 60 English words (count the words!)
            - Author description: EXACTLY 60 English words (count the words!)
            - Book summary: EXACTLY 100 English words (count the words!)
            - Use appropriate emojis: Fiction 📖, Science 🔬, History 📜, Philosophy 🤔, Romance 💕, Mystery 🔍, Biography 👤, Poetry 📝
            - Use real Wikipedia links when possible
            - Be detailed and informative

            Remember: Each description must be exactly the specified word count. No more, no less.
            """

        try:
            import time
            # Add small delay to avoid rate limiting
            time.sleep(0.5)

            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise content generator. You MUST follow word count requirements exactly. Count words carefully before responding."
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.0,  # Zero temperature for fastest, most deterministic results
                max_tokens=1200,  # Increased tokens for longer descriptions
                timeout=12  # Slightly longer timeout for detailed descriptions
            )

            response = json.loads(chat_completion.choices[0].message.content)

            # Post-process to ensure word counts are correct
            categories = response.get('categories', [])
            for cat in categories:
                desc = cat.get('description', '')
                cat['description'] = self._ensure_word_count(desc, 60, language)

            author = response.get('author', {})
            if author and 'description' in author:
                author['description'] = self._ensure_word_count(author['description'], 60, language)

            book_summary = response.get('book_summary', '')
            book_summary = self._ensure_word_count(book_summary, 100, language)

            return {
                "categories": categories,
                "author": author,
                "book_summary": book_summary
            }

        except Exception as e:
            print(f"LLM combined structured info error: {e}")
            # Fallback to simple structure with proper word counts
            fallback_desc = "This is a literary category that encompasses various works and themes in literature and writing." if language == 'en' else "هذه فئة أدبية تشمل أعمالاً وموضوعات مختلفة في الأدب والكتابة."
            fallback_author_desc = "This author has contributed significantly to literature through their various works and writings." if language == 'en' else "هذا المؤلف ساهم بشكل كبير في الأدب من خلال أعماله وكتاباته المختلفة."
            fallback_summary = "This book represents an important work in literature that explores various themes and characters through engaging storytelling." if language == 'en' else "هذا الكتاب يمثل عملاً مهماً في الأدب يستكشف موضوعات وشخصيات مختلفة من خلال السرد الممتع."

            # Translate category names to Arabic if needed
            translated_categories = []
            for cat in categories:
                if language == 'ar':
                    # Simple translation mapping for common categories
                    arabic_translations = {
                        'fiction': 'خيال', 'romance': 'رومانسية', 'history': 'تاريخ',
                        'science': 'علوم', 'philosophy': 'فلسفة', 'poetry': 'شعر',
                        'novel': 'رواية', 'biography': 'سيرة ذاتية', 'mystery': 'غموض',
                        'adventure': 'مغامرة', 'drama': 'دراما', 'comedy': 'كوميديا',
                        'literature': 'أدب', 'courtship': 'خطوبة', 'classic': 'كلاسيكي'
                    }
                    translated_name = arabic_translations.get(cat.lower() if cat else '', cat)
                    translated_categories.append(translated_name)
                else:
                    translated_categories.append(cat)

            # Create categories with proper icons
            categories_with_icons = []
            for cat in translated_categories:
                # Map categories to appropriate icons
                icon_mapping = {
                    'خيال': '📖', 'fiction': '📖',
                    'رومانسية': '💕', 'romance': '💕',
                    'تاريخ': '📜', 'history': '📜',
                    'علوم': '🔬', 'science': '🔬',
                    'فلسفة': '🤔', 'philosophy': '🤔',
                    'شعر': '📝', 'poetry': '📝',
                    'رواية': '📖', 'novel': '📖',
                    'سيرة ذاتية': '👤', 'biography': '👤',
                    'غموض': '🔍', 'mystery': '🔍',
                    'مغامرة': '⚔️', 'adventure': '⚔️',
                    'دراما': '🎭', 'drama': '🎭',
                    'كوميديا': '😄', 'comedy': '😄',
                    'أدب': '📚', 'literature': '📚',
                    'خطوبة': '💍', 'courtship': '💍',
                    'كلاسيكي': '🏛️', 'classic': '🏛️'
                }

                icon = icon_mapping.get(cat.lower() if cat else '', '📚')  # Default to book icon
                categories_with_icons.append({
                    "name": cat,
                    "icon": icon,
                    "wikilink": "",
                    "description": self._ensure_word_count(fallback_desc, 60, language)
                })

            return {
                "categories": categories_with_icons,
                "author": {
                    "name": author_name,
                    "image": f"https://ui-avatars.com/api/?name={author_name.replace(' ', '+')}&size=300&background=4f46e5&color=ffffff&format=png&length=10&font-size=0.4",
                    "wikilink": "",
                    "profession": ["كاتب"] if language == 'ar' else ["Writer"],
                    "descriptions": [
                        self._ensure_word_count(fallback_author_desc, 60, language),
                        "معلومات إضافية عن المؤلف" if language == 'ar' else "Additional information about the author"
                    ]
                },
                "book_summary": self._ensure_word_count(fallback_summary, 100, language)
            }

    def analyze_description_for_categories(self, description: str, language: str = 'en') -> Dict:
        """
        Analyze a book description and extract categories with detailed information.

        Args:
            description: Book description text
            language: Language code ('en' or 'ar')

        Returns:
            Dict containing categories and analysis summary
        """
        if language == 'ar':
            prompt = f"""
            تحليل وصف الكتاب التالي وتحديد الفئات المناسبة له:

            "{description}"

            قم بإنشاء معلومات منظمة بتنسيق JSON:
            {{
                "categories": [
                    {{
                        "name": "اسم الفئة بالعربية",
                        "icon": "رمز تعبيري مناسب",
                        "wikilink": "https://ar.wikipedia.org/wiki/...",
                        "description": "وصف مفصل للفئة من 100 كلمة عربية بالضبط"
                    }}
                ],
                "analysis_summary": "ملخص موجز لتحليل الوصف وسبب اختيار هذه الفئات"
            }}

            ملاحظات مهمة:
            - حدد 1-3 فئات رئيسية فقط بناءً على الوصف
            - يجب أن يكون وصف كل فئة 100 كلمة عربية بالضبط
            - استخدم رموز تعبيرية مناسبة: أدب 📖، تاريخ 📜، علوم 🔬، فلسفة 🤔، رومانسية 💕، غموض 🔍، سيرة ذاتية 👤، شعر 📝
            - استخدم روابط ويكيبيديا عربية حقيقية
            - قدم تحليلاً موجزاً يشرح سبب اختيار هذه الفئات
            """
        else:
            prompt = f"""
            Analyze the following book description and identify appropriate categories:

            "{description}"

            Create structured information in JSON format:
            {{
                "categories": [
                    {{
                        "name": "Category Name",
                        "icon": "Appropriate emoji",
                        "wikilink": "https://en.wikipedia.org/wiki/...",
                        "description": "Exactly 100 English words describing this literary category, its characteristics, typical themes, writing styles, and what makes books in this category unique. Focus on the literary genre itself, not general descriptions."
                    }}
                ],
                "analysis_summary": "Brief summary of the analysis and why these categories were chosen"
            }}

            Important notes:
            - Identify only 1-3 main categories based on the description
            - Each category description must be exactly 100 words
            - Use appropriate emojis: Fiction 📖, History 📜, Science 🔬, Philosophy 🤔, Romance 💕, Mystery 🔍, Biography 👤, Poetry 📝
            - Use real English Wikipedia links
            - Provide a brief analysis explaining why these categories were chosen
            """

        try:
            import time
            # Add small delay to avoid rate limiting
            time.sleep(0.5)

            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise content generator. You MUST follow word count requirements exactly. Count words carefully before responding."
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.0,  # Zero temperature for fastest, most deterministic results
                max_tokens=1200,  # Increased tokens for longer descriptions
                timeout=12  # Slightly longer timeout for detailed descriptions
            )

            response = json.loads(chat_completion.choices[0].message.content)

            # Post-process to ensure word counts are correct
            categories = response.get('categories', [])
            for cat in categories:
                desc = cat.get('description', '')
                cat['description'] = self._ensure_word_count(desc, 100, language)

            return {
                "categories": categories,
                "analysis_summary": response.get('analysis_summary', '')
            }

        except Exception as e:
            print(f"LLM description analysis error: {e}")
            # Fallback to simple structure with proper word counts
            fallback_desc = "This category encompasses works that explore themes and ideas through narrative or informative content. It includes various styles and approaches to storytelling or knowledge sharing, appealing to different audiences with diverse interests and preferences." if language == 'en' else "تشمل هذه الفئة الأعمال التي تستكشف الموضوعات والأفكار من خلال المحتوى السردي أو المعلوماتي. وتتضمن أساليب ومناهج مختلفة لرواية القصص أو مشاركة المعرفة، وتجذب جماهير مختلفة ذات اهتمامات وتفضيلات متنوعة."

            return {
                "categories": [
                    {
                        "name": "Literature" if language == 'en' else "الأدب",
                        "icon": "📚",
                        "wikilink": "https://en.wikipedia.org/wiki/Literature" if language == 'en' else "https://ar.wikipedia.org/wiki/أدب",
                        "description": self._ensure_word_count(fallback_desc, 100, language)
                    }
                ],
                "analysis_summary": "Analysis based on the provided description." if language == 'en' else "تحليل بناءً على الوصف المقدم."
            }

    def _ensure_word_count(self, text: str, target_words: int, language: str = 'en') -> str:
        """
        Ensure text meets the target word count by extending or trimming as needed.

        Args:
            text: Original text
            target_words: Target word count
            language: Language for extensions

        Returns:
            Text with correct word count
        """
        if not text:
            return ""

        words = text.split()
        current_count = len(words)

        if current_count == target_words:
            return text
        elif current_count > target_words:
            # Trim to target length
            return ' '.join(words[:target_words])
        else:
            # Extend to target length

            if language == 'ar':
                # Arabic filler words and phrases
                fillers = [
                    "وهو مهم جداً", "في هذا المجال", "من خلال هذا العمل", "بطريقة مميزة",
                    "وله تأثير كبير", "على القراء والمهتمين", "في الثقافة العربية", "والأدب العالمي",
                    "مما يجعله مرجعاً مهماً", "للدارسين والباحثين", "في هذا التخصص", "والمجالات المرتبطة",
                    "وقد حقق نجاحاً واسعاً", "بين النقاد والقراء", "على حد سواء", "في العالم العربي"
                ]
            else:
                # English filler words and phrases
                fillers = [
                    "which is very important", "in this field", "through this work", "in a distinctive way",
                    "and has great impact", "on readers and enthusiasts", "in literary culture", "and world literature",
                    "making it an important reference", "for students and researchers", "in this specialty", "and related fields",
                    "and has achieved wide success", "among critics and readers", "alike throughout", "the literary world"
                ]

            # Add filler words until we reach target
            filler_index = 0
            while len(words) < target_words and filler_index < len(fillers):
                filler_words = fillers[filler_index].split()
                words_to_add = min(len(filler_words), target_words - len(words))
                words.extend(filler_words[:words_to_add])
                filler_index += 1

            # If still short, repeat some fillers
            while len(words) < target_words:
                words.append("والمزيد" if language == 'ar' else "and more")

            return ' '.join(words[:target_words])

    def get_structured_categories(self, categories: List[str], book_title: str = "", book_author: str = "", language: str = 'en') -> List[Dict]:
        """
        Get structured category information with icons and wiki links.

        Args:
            categories: List of category names
            book_title: Book title for context
            book_author: Book author for context
            language: Target language

        Returns:
            List of structured category objects
        """
        if not categories:
            return []

        categories_str = ", ".join(categories)

        if language == 'ar':
            prompt = f"""
            للكتاب "{book_title}" للمؤلف "{book_author}" مع الفئات: {categories_str}

            أنشئ معلومات منظمة لكل فئة بتنسيق JSON:
            {{
                "categories": [
                    {{
                        "name": "اسم الفئة",
                        "icon": "📚",
                        "wikilink": "https://ar.wikipedia.org/wiki/...",
                        "description": "وصف مختصر للفئة"
                    }}
                ]
            }}

            استخدم أيقونات مناسبة وروابط ويكيبيديا عربية حقيقية.
            """
        else:
            prompt = f"""
            For the book "{book_title}" by "{book_author}" with categories: {categories_str}

            Create structured information for each category in JSON format:
            {{
                "categories": [
                    {{
                        "name": "Category Name",
                        "icon": "📚",
                        "wikilink": "https://en.wikipedia.org/wiki/...",
                        "description": "50-100 word description of the category"
                    }}
                ]
            }}

            IMPORTANT: Each description must be exactly 50-100 words.
            Use appropriate emojis as icons and real Wikipedia links.
            Common category icons: Fiction 📖, Science 🔬, History 📜, Philosophy 🤔, Romance 💕, Mystery 🔍, Biography 👤, Poetry 📝
            """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            response = json.loads(chat_completion.choices[0].message.content)
            return response.get('categories', [])

        except Exception as e:
            print(f"LLM structured categories error: {e}")
            # Fallback to simple structure
            return [{"name": cat, "icon": "📚", "wikilink": "", "description": ""} for cat in categories]

    def get_structured_author_info(self, author_name: str, book_title: str = "", language: str = 'en') -> Dict:
        """
        Get structured author information with picture, wiki link, and profession.

        Args:
            author_name: Author's name
            book_title: Book title for context
            language: Target language

        Returns:
            Structured author object
        """
        if not author_name:
            return {}

        if language == 'ar':
            prompt = f"""
            للمؤلف "{author_name}" الذي كتب "{book_title}"

            أنشئ معلومات منظمة بتنسيق JSON:
            {{
                "author": {{
                    "name": "{author_name}",
                    "pic": "رابط صورة حقيقية أو مسار افتراضي",
                    "wikilink": "https://ar.wikipedia.org/wiki/...",
                    "profession": "المهنة",
                    "description": "وصف مختصر للمؤلف"
                }}
            }}

            استخدم روابط ويكيبيديا عربية حقيقية إذا كانت متوفرة.
            """
        else:
            prompt = f"""
            For author "{author_name}" who wrote "{book_title}"

            Create structured information in JSON format:
            {{
                "author": {{
                    "name": "{author_name}",
                    "pic": "real image URL - try to find actual author photo URLs from Wikipedia, Goodreads, or other reliable sources",
                    "wikilink": "https://en.wikipedia.org/wiki/...",
                    "profession": "writer/novelist/poet/etc",
                    "description": "50-100 word description of the author"
                }}
            }}

            IMPORTANT:
            - The description must be exactly 50-100 words.
            - For pic, try to provide real author image URLs from reliable sources like Wikipedia Commons, Goodreads, or OpenLibrary
            - Use real Wikipedia links if available
            - If no real image URL is available, use: "https://ui-avatars.com/api/?name={author_name.replace(' ', '+')}&size=300&background=6366f1&color=ffffff&format=png"
            """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            response = json.loads(chat_completion.choices[0].message.content)
            return response.get('author', {})

        except Exception as e:
            print(f"LLM structured author error: {e}")
            # Fallback to simple structure
            return {
                "name": author_name,
                "pic": "/static/images/authors/default.jpg",
                "wikilink": "",
                "profession": "writer",
                "description": ""
            }

    def translate_categories(self, categories: List[str], target_language: str) -> List[str]:
        """
        Translate book categories to target language.
        
        Args:
            categories: List of categories to translate
            target_language: Target language ('en' or 'ar')
            
        Returns:
            List of translated categories
        """
        
        if not categories:
            return []
        
        categories_str = ', '.join(categories)
        
        if target_language == 'ar':
            prompt = f"""
            ترجم الفئات التالية إلى العربية: {categories_str}
            
            أجب بتنسيق JSON فقط:
            {{
                "translated_categories": ["الفئة الأولى", "الفئة الثانية"]
            }}
            
            استخدم مصطلحات عربية مناسبة للمكتبات والكتب.
            """
        else:
            prompt = f"""
            Translate the following categories to English: {categories_str}
            
            Respond in JSON format only:
            {{
                "translated_categories": ["Category 1", "Category 2"]
            }}
            
            Use appropriate English terms for library and book categories.
            """
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            
            response = json.loads(chat_completion.choices[0].message.content)
            return response.get('translated_categories', categories)
            
        except Exception as e:
            print(f"LLM translation error: {e}")
            return categories
    
    def _fallback_extraction(self, query: str, language: str) -> Dict:
        """Fallback extraction when LLM fails."""
        return {
            'title': query,
            'author': None,
            'categories': [],
            'language': language,
            'search_variations': [query],
            'description': None,
            'is_arabic_query': language == 'ar'
        }

    def find_pdf_link(self, title: str, author: str, language: str = 'en') -> Optional[str]:
        """
        Use LLM to find a PDF link for a book when APIs don't provide one.

        Args:
            title: Book title
            author: Book author
            language: Book language

        Returns:
            PDF URL if found, None otherwise
        """
        # Create prompt based on language
        if language == 'ar':
            prompt = f"""
            ابحث عن رابط تحميل مباشر لملف PDF للكتاب "{title}" للمؤلف "{author}".

            أجب بتنسيق JSON فقط:
            {{
                "pdf_url": "https://example.com/book.pdf",
                "source": "اسم المصدر",
                "confidence": 0.8
            }}

            متطلبات مهمة:
            - أعطني فقط روابط تنتهي بـ .pdf أو تحتوي على /download/ وتؤدي إلى ملفات PDF فعلية
            - لا تعطني صفحات HTML أو صفحات بحث أو صفحات معلومات الكتاب
            - ركز على المصادر الموثوقة مثل:
              * Internet Archive (archive.org/download/...)
              * Project Gutenberg نسخ PDF
              * المكتبات الرقمية العربية
            - إذا لم تتمكن من العثور على رابط تحميل PDF مباشر، استخدم null للـ pdf_url
            """
        else:
            prompt = f"""
            Find a direct PDF download link for the book "{title}" by "{author}".

            Respond in JSON format only:
            {{
                "pdf_url": "https://example.com/book.pdf",
                "source": "source name",
                "confidence": 0.8
            }}

            IMPORTANT REQUIREMENTS:
            - Only return URLs that end with .pdf or contain /download/ and lead to actual PDF files
            - Do NOT return HTML pages, search pages, or book information pages
            - Focus on reliable sources like:
              * Internet Archive (archive.org/download/...)
              * Project Gutenberg PDF versions (gutenberg.org/files/.../filename.pdf)
              * ManyBooks (manybooks.net/download/...)
              * Open Library PDF downloads
            - If you cannot find a DIRECT PDF download link, use null for pdf_url
            - Verify the URL structure suggests it's a direct PDF download
            """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            response = json.loads(chat_completion.choices[0].message.content)
            pdf_url = response.get('pdf_url')

            # Validate URL format and ensure it's likely a PDF
            if pdf_url and self._is_valid_pdf_url(pdf_url):
                return pdf_url
            return None

        except Exception as e:
            print(f"LLM PDF link search error: {e}")
            return None

    def _is_valid_pdf_url(self, url: str) -> bool:
        """Validate if a URL is likely to be a direct PDF download link."""
        if not url or not (url.startswith('http://') or url.startswith('https://')):
            return False

        url_lower = url.lower() if url else ''

        # Check if URL ends with .pdf
        if url_lower.endswith('.pdf'):
            return True

        # Check for common PDF download patterns
        pdf_patterns = [
            '/download/',
            'download.php',
            'get.php',
            'files/',
            '.pdf?',
            'format=pdf',
            'type=pdf'
        ]

        for pattern in pdf_patterns:
            if pattern in url_lower:
                return True

        # Exclude obvious non-PDF URLs
        exclude_patterns = [
            '.html',
            '.htm',
            '/search',
            '/browse',
            '/catalog',
            'search.php',
            'index.php',
            '-h.htm',  # Gutenberg HTML versions
            '.txt'
        ]

        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        # If none of the PDF patterns matched, it's probably not a PDF
        return False

    def find_multiple_pdf_links(self, title: str, author: str, language: str = 'en') -> List[str]:
        """
        Use LLM to find multiple PDF links for a book, prioritizing reliable sources.

        Args:
            title: Book title
            author: Book author
            language: Book language

        Returns:
            List of potential PDF URLs, ordered by reliability
        """
        # Create enhanced prompt for multiple sources
        if language == 'ar':
            prompt = f"""
            ابحث عن روابط تحميل PDF متعددة للكتاب "{title}" للمؤلف "{author}".

            أجب بتنسيق JSON فقط:
            {{
                "pdf_urls": [
                    {{
                        "url": "https://archive.org/download/identifier/book.pdf",
                        "source": "Internet Archive",
                        "reliability": 0.9
                    }},
                    {{
                        "url": "https://www.gutenberg.org/files/123/123.pdf",
                        "source": "Project Gutenberg",
                        "reliability": 0.95
                    }}
                ]
            }}

            متطلبات:
            - ابحث في المصادر الموثوقة: Internet Archive, Project Gutenberg, المكتبات الرقمية
            - أعطني فقط روابط PDF مباشرة تنتهي بـ .pdf
            - رتب النتائج حسب الموثوقية (reliability)
            - إذا لم تجد أي روابط، أرجع قائمة فارغة
            """
        else:
            prompt = f"""
            Find multiple direct PDF download links for the book "{title}" by "{author}".

            Respond in JSON format only:
            {{
                "pdf_urls": [
                    {{
                        "url": "https://archive.org/download/identifier/book.pdf",
                        "source": "Internet Archive",
                        "reliability": 0.9
                    }},
                    {{
                        "url": "https://www.gutenberg.org/files/123/123.pdf",
                        "source": "Project Gutenberg",
                        "reliability": 0.95
                    }}
                ]
            }}

            Requirements:
            - Search reliable sources: Internet Archive, Project Gutenberg, digital libraries
            - Only return direct PDF download URLs ending with .pdf
            - Order results by reliability score (0.0 to 1.0)
            - Focus on public domain and open access books
            - If no PDFs found, return empty array
            - Verify URL patterns match known working sources
            """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model,
                response_format={"type": "json_object"},
                temperature=0.2,  # Lower temperature for more consistent results
            )

            response = json.loads(chat_completion.choices[0].message.content)
            pdf_urls_data = response.get('pdf_urls', [])

            # Extract and validate URLs
            valid_urls = []
            for pdf_data in pdf_urls_data:
                url = pdf_data.get('url', '')
                if url and self._is_valid_pdf_url(url):
                    valid_urls.append(url)

            return valid_urls

        except Exception as e:
            print(f"LLM multiple PDF search error: {e}")
            # Fallback to single PDF search
            single_url = self.find_pdf_link(title, author, language)
            return [single_url] if single_url else []

