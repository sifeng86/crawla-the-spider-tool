"""
-----
soup:
-----
find
find_all
select
find_by_class
find_by_id
find_by_tag
find_by_text
--------
selenium:
--------
find_element_by_id(id_)
find_elements_by_id(id_)
find_element_by_class_name(name)
find_elements_by_class_name(name)
find_element_by_css_selector(css_selector)
find_elements_by_css_selector(css_selector)
find_element_by_xpath(xpath)
find_elements_by_xpath(xpath)
find_element_by_link_text(text)
find_elements_by_link_text(text)
"""


class stepHelper:

    def get_soup_steps_helper():

        helper = {
            'find_element_by_id': '.find(id="{param}")',
            'find_elements_by_id': '.find_all(id="{param}")',
            'find_element_by_class': '.find(class_="{param}")',
            'find_elements_by_class': '.find_all(class_="{param}")',
            'select_one': '.select("{param}")[0]',
            'select_all': '.select("{param}")',
            'ext_str_get_text': '.get_text()'
        }

        return helper
    
    def get_selenium_steps_helper():

        helper = {
            "find_element_by_id": '.find_element_by_id("{param}")',
            "find_elements_by_id": '.find_elements_by_id("{param}")',
            "find_element_by_class": '.find_element_by_class_name("{param}")',
            "find_elements_by_class": '.find_elements_by_class_name("{param}")',
            "find_element_by_css_selector": '.find_element_by_css_selector("{param}")',
            "find_elements_by_css_selector": '.find_elements_by_css_selector("{param}")',
            "click": '.click()',
            "ext_str_get_text": '.text',
            "ext_str_get_attribute": '.get_attribute("{param}")'
        }

        return helper

