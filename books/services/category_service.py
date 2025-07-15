"""
Category Service for mapping and localizing book categories.
Handles predefined category lists and LLM-based category translation.
"""

from typing import List, Dict, Optional
from .llm_service import LLMService


class CategoryService:
    """Service for category mapping and localization."""
    
    def __init__(self):
        self.llm_service = LLMService()
        
        # Predefined category mappings (English -> Arabic)
        self.category_mappings = {
            # Literature and Fiction
            'fiction': 'الخيال',
            'literature': 'الأدب',
            'novel': 'الرواية',
            'poetry': 'الشعر',
            'drama': 'المسرح',
            'short stories': 'القصص القصيرة',
            'classic literature': 'الأدب الكلاسيكي',
            'modern literature': 'الأدب الحديث',
            'arabic literature': 'الأدب العربي',
            'world literature': 'الأدب العالمي',
            
            # Non-Fiction
            'biography': 'السيرة الذاتية',
            'autobiography': 'السيرة الذاتية',
            'memoir': 'المذكرات',
            'history': 'التاريخ',
            'philosophy': 'الفلسفة',
            'religion': 'الدين',
            'islamic studies': 'الدراسات الإسلامية',
            'theology': 'علم اللاهوت',
            'spirituality': 'الروحانية',
            
            # Sciences
            'science': 'العلوم',
            'physics': 'الفيزياء',
            'chemistry': 'الكيمياء',
            'biology': 'الأحياء',
            'mathematics': 'الرياضيات',
            'medicine': 'الطب',
            'psychology': 'علم النفس',
            'sociology': 'علم الاجتماع',
            'anthropology': 'علم الإنسان',
            
            # Arts and Culture
            'art': 'الفن',
            'music': 'الموسيقى',
            'painting': 'الرسم',
            'sculpture': 'النحت',
            'architecture': 'العمارة',
            'photography': 'التصوير',
            'cinema': 'السينما',
            'theater': 'المسرح',
            
            # Education and Reference
            'education': 'التعليم',
            'textbook': 'كتاب مدرسي',
            'reference': 'المراجع',
            'dictionary': 'القاموس',
            'encyclopedia': 'الموسوعة',
            'manual': 'الدليل',
            'guide': 'الدليل',
            
            # Business and Economics
            'business': 'الأعمال',
            'economics': 'الاقتصاد',
            'finance': 'المالية',
            'management': 'الإدارة',
            'marketing': 'التسويق',
            'entrepreneurship': 'ريادة الأعمال',
            
            # Technology
            'technology': 'التكنولوجيا',
            'computer science': 'علوم الحاسوب',
            'programming': 'البرمجة',
            'artificial intelligence': 'الذكاء الاصطناعي',
            'engineering': 'الهندسة',
            
            # Children and Young Adult
            'children': 'الأطفال',
            'young adult': 'الشباب',
            'juvenile': 'الأحداث',
            'picture book': 'كتاب مصور',
            
            # Genres
            'mystery': 'الغموض',
            'thriller': 'الإثارة',
            'romance': 'الرومانسية',
            'adventure': 'المغامرة',
            'fantasy': 'الخيال',
            'science fiction': 'الخيال العلمي',
            'horror': 'الرعب',
            'crime': 'الجريمة',
            'detective': 'التحقيق',
            
            # Other
            'travel': 'السفر',
            'cooking': 'الطبخ',
            'health': 'الصحة',
            'fitness': 'اللياقة البدنية',
            'sports': 'الرياضة',
            'politics': 'السياسة',
            'law': 'القانون',
            'journalism': 'الصحافة',
            'self-help': 'المساعدة الذاتية',
            'personal development': 'التطوير الشخصي'
        }
        
        # Reverse mapping (Arabic -> English)
        self.reverse_mappings = {v: k for k, v in self.category_mappings.items()}
        
        # Predefined category lists for different contexts
        self.library_categories = {
            'en': [
                'Fiction', 'Non-Fiction', 'Biography', 'History', 'Science',
                'Philosophy', 'Religion', 'Art', 'Literature', 'Poetry',
                'Drama', 'Children', 'Young Adult', 'Reference', 'Education',
                'Business', 'Technology', 'Health', 'Travel', 'Cooking'
            ],
            'ar': [
                'الخيال', 'غير الخيال', 'السيرة الذاتية', 'التاريخ', 'العلوم',
                'الفلسفة', 'الدين', 'الفن', 'الأدب', 'الشعر',
                'المسرح', 'الأطفال', 'الشباب', 'المراجع', 'التعليم',
                'الأعمال', 'التكنولوجيا', 'الصحة', 'السفر', 'الطبخ'
            ]
        }
    
    def get_predefined_categories(self, language: str = 'en') -> List[str]:
        """
        Get predefined category list for a specific language.
        
        Args:
            language: Target language ('en' or 'ar')
            
        Returns:
            List of predefined categories
        """
        return self.library_categories.get(language, self.library_categories['en'])
    
    def map_category(self, category: str, target_language: str) -> str:
        """
        Map a category to target language using predefined mappings.
        
        Args:
            category: Category to map
            target_language: Target language ('en' or 'ar')
            
        Returns:
            Mapped category or original if no mapping found
        """
        if not category:
            return category
        
        category_lower = category.lower().strip()
        
        if target_language == 'ar':
            # English to Arabic
            return self.category_mappings.get(category_lower, category)
        elif target_language == 'en':
            # Arabic to English
            return self.reverse_mappings.get(category, category)
        
        return category
    
    def map_categories_list(self, categories: List[str], target_language: str) -> List[str]:
        """
        Map a list of categories to target language.
        
        Args:
            categories: List of categories to map
            target_language: Target language ('en' or 'ar')
            
        Returns:
            List of mapped categories
        """
        if not categories:
            return []
        
        mapped_categories = []
        for category in categories:
            mapped = self.map_category(category, target_language)
            if mapped and mapped not in mapped_categories:
                mapped_categories.append(mapped)
        
        return mapped_categories
    
    def enhance_categories_with_llm(self, categories: List[str], book_title: str, book_author: str, target_language: str = 'en') -> List[str]:
        """
        Enhance categories using LLM to suggest additional relevant categories.
        
        Args:
            categories: Existing categories
            book_title: Book title for context
            book_author: Book author for context
            target_language: Target language for suggestions
            
        Returns:
            Enhanced list of categories
        """
        try:
            # First, map existing categories
            mapped_categories = self.map_categories_list(categories, target_language)
            
            # Get predefined categories for reference
            predefined = self.get_predefined_categories(target_language)
            
            # Use LLM to suggest additional categories
            if target_language == 'ar':
                prompt = f"""
                بناءً على الكتاب "{book_title}" للمؤلف "{book_author}" والفئات الحالية: {', '.join(mapped_categories)}
                
                اقترح فئات إضافية مناسبة من القائمة التالية: {', '.join(predefined)}
                
                أجب بتنسيق JSON فقط:
                {{
                    "suggested_categories": ["الفئة الأولى", "الفئة الثانية"],
                    "final_categories": ["جميع الفئات المناسبة"]
                }}
                
                لا تقترح أكثر من 5 فئات إجمالية.
                """
            else:
                prompt = f"""
                Based on the book "{book_title}" by "{book_author}" and current categories: {', '.join(mapped_categories)}
                
                Suggest additional appropriate categories from this list: {', '.join(predefined)}
                
                Respond in JSON format only:
                {{
                    "suggested_categories": ["Category 1", "Category 2"],
                    "final_categories": ["All appropriate categories"]
                }}
                
                Don't suggest more than 5 total categories.
                """
            
            enhanced_categories = self.llm_service.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.llm_service.model,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            
            import json
            response = json.loads(enhanced_categories.choices[0].message.content)
            final_categories = response.get('final_categories', mapped_categories)
            
            # Ensure we don't exceed reasonable limits
            return final_categories[:5] if len(final_categories) > 5 else final_categories
            
        except Exception as e:
            print(f"LLM category enhancement error: {e}")
            return mapped_categories
    
    def normalize_category(self, category: str, target_language: str = 'en') -> str:
        """
        Normalize a category string (clean up, standardize format).
        
        Args:
            category: Category to normalize
            target_language: Target language for normalization
            
        Returns:
            Normalized category
        """
        if not category:
            return ''
        
        # Clean up the category
        normalized = category.strip()
        
        # Remove extra spaces
        normalized = ' '.join(normalized.split())
        
        # Map to standard form if available
        mapped = self.map_category(normalized, target_language)
        
        return mapped
    
    def suggest_categories_for_book(self, book_title: str, book_author: str = '', book_description: str = '', target_language: str = 'en') -> List[str]:
        """
        Suggest categories for a book based on its metadata.
        
        Args:
            book_title: Book title
            book_author: Book author
            book_description: Book description
            target_language: Target language for suggestions
            
        Returns:
            List of suggested categories
        """
        try:
            predefined = self.get_predefined_categories(target_language)
            
            if target_language == 'ar':
                prompt = f"""
                اقترح فئات مناسبة للكتاب التالي:
                العنوان: "{book_title}"
                المؤلف: "{book_author}"
                الوصف: "{book_description[:500]}"
                
                اختر من الفئات التالية: {', '.join(predefined)}
                
                أجب بتنسيق JSON فقط:
                {{
                    "categories": ["الفئة الأولى", "الفئة الثانية", "الفئة الثالثة"]
                }}
                
                اقترح 2-4 فئات مناسبة فقط.
                """
            else:
                prompt = f"""
                Suggest appropriate categories for the following book:
                Title: "{book_title}"
                Author: "{book_author}"
                Description: "{book_description[:500]}"
                
                Choose from these categories: {', '.join(predefined)}
                
                Respond in JSON format only:
                {{
                    "categories": ["Category 1", "Category 2", "Category 3"]
                }}
                
                Suggest only 2-4 appropriate categories.
                """
            
            response = self.llm_service.client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=self.llm_service.model,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            suggested_categories = result.get('categories', [])
            
            return suggested_categories[:4]  # Limit to 4 categories
            
        except Exception as e:
            print(f"Category suggestion error: {e}")
            # Fallback to basic categorization
            if target_language == 'ar':
                return ['الأدب']  # Default to Literature in Arabic
            else:
                return ['Literature']  # Default to Literature in English
    
    def validate_category(self, category: str, language: str = 'en') -> bool:
        """
        Validate if a category is in the predefined list.
        
        Args:
            category: Category to validate
            language: Language of the category
            
        Returns:
            True if category is valid, False otherwise
        """
        if not category:
            return False
        
        predefined = self.get_predefined_categories(language)
        return category in predefined or category.lower() in [c.lower() for c in predefined]
    
    def get_category_hierarchy(self, category: str, language: str = 'en') -> Dict:
        """
        Get category hierarchy information (parent/child relationships).
        This is a simplified version - in a full implementation, you might have a more complex hierarchy.
        
        Args:
            category: Category to get hierarchy for
            language: Language of the category
            
        Returns:
            Dict with hierarchy information
        """
        # Simplified hierarchy mapping
        hierarchies = {
            'en': {
                'Fiction': {'parent': 'Literature', 'children': ['Novel', 'Short Stories', 'Poetry']},
                'Non-Fiction': {'parent': None, 'children': ['Biography', 'History', 'Science']},
                'Science': {'parent': 'Non-Fiction', 'children': ['Physics', 'Chemistry', 'Biology']},
                'Literature': {'parent': None, 'children': ['Fiction', 'Poetry', 'Drama']},
            },
            'ar': {
                'الخيال': {'parent': 'الأدب', 'children': ['الرواية', 'القصص القصيرة', 'الشعر']},
                'غير الخيال': {'parent': None, 'children': ['السيرة الذاتية', 'التاريخ', 'العلوم']},
                'العلوم': {'parent': 'غير الخيال', 'children': ['الفيزياء', 'الكيمياء', 'الأحياء']},
                'الأدب': {'parent': None, 'children': ['الخيال', 'الشعر', 'المسرح']},
            }
        }
        
        return hierarchies.get(language, {}).get(category, {'parent': None, 'children': []})

